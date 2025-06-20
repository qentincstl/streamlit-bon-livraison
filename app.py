# app.py
import streamlit as st
import pandas as pd
import requests, io, re
import fitz  # PyMuPDF

st.set_page_config(page_title="Fiche de réception", layout="wide")
st.title("📥 Documents de réception → FICHE DE RÉCEPTION")

# 1) Extraction texte PDF numérique
def extract_pdf_text(uploaded_file) -> str:
    try:
        uploaded_file.seek(0)
        data = uploaded_file.read()
        doc = fitz.open(stream=data, filetype="pdf")
        return "\n".join(page.get_text() for page in doc)
    except:
        return ""

# 2) OCR.space avec MIME correct
def ocr_space_file(uploaded_file) -> str:
    api_key = st.secrets.get("OCR_SPACE_API_KEY", "")
    if not api_key:
        st.error("🛑 Clé OCR_SPACE_API_KEY manquante dans les Secrets")
        return ""
    uploaded_file.seek(0)
    data = uploaded_file.read()
    ext = uploaded_file.name.lower().split(".")[-1]
    if ext == "pdf":
        mime = "application/pdf"
    elif ext in ("jpg","jpeg"):
        mime = "image/jpeg"
    elif ext == "png":
        mime = "image/png"
    else:
        st.error(f"🛑 Format non supporté: .{ext}")
        return ""
    files = {"file": (uploaded_file.name, data, mime)}
    payload = {"apikey": api_key, "language": "fre", "isOverlayRequired": False}
    resp = requests.post("https://api.ocr.space/parse/image",
                         files=files, data=payload, timeout=60)
    if resp.status_code!=200:
        st.error(f"🛑 Erreur HTTP {resp.status_code} OCR.space")
        st.text(resp.text)
        return ""
    j = resp.json()
    if j.get("IsErroredOnProcessing"):
        st.error("🛑 OCR.space:", j["ErrorMessage"][0])
        return ""
    return "\n".join(p["ParsedText"] for p in j.get("ParsedResults",[]))

# 3) Parsing très souple : cherche au moins 3 nombres dans une ligne
def parse_text_to_df(raw: str) -> pd.DataFrame:
    rows = []
    for line in raw.splitlines():
        # on capture tous les chiffres de la ligne
        nums = re.findall(r"\d+", line)
        if len(nums) >= 3:
            # on prend les 3 premiers comme Réf / Nb colis / pcs colis
            ref, colis, pcs = nums[0], nums[1], nums[2]
            rows.append({
                "Référence": ref,
                "Nb de colis": int(colis),
                "pcs par colis": int(pcs),
                "total": int(colis)*int(pcs),
                "Vérification": ""
            })
    if not rows:
        st.warning("⚠️ Aucune ligne valide détectée.")
    return pd.DataFrame(rows)

# 4) Lecture Excel d'entrée
def read_excel_to_df(buf: io.BytesIO) -> pd.DataFrame:
    df = pd.read_excel(buf)
    df = df.rename(columns={
        df.columns[0]:"Référence",
        df.columns[1]:"Nb de colis",
        df.columns[2]:"pcs par colis"
    })
    df["total"] = df["Nb de colis"] * df["pcs par colis"]
    df["Vérification"] = ""
    return df[["Référence","Nb de colis","pcs par colis","total","Vérification"]]

# --- Interface ---
uploaded = st.file_uploader(
    "📂 Déposez un PDF, JPG/PNG ou fichier Excel (.xlsx)",
    type=["pdf","jpg","jpeg","png","xlsx"]
)

if uploaded:
    ext = uploaded.name.lower().split(".")[-1]
    # 4. si Excel
    if ext == "xlsx":
        df = read_excel_to_df(io.BytesIO(uploaded.read()))
    else:
        # 1. PDF textuel d'abord
        raw = ""
        if ext=="pdf":
            raw = extract_pdf_text(uploaded)
        # 2. sinon OCR
        if not raw.strip():
            raw = ocr_space_file(uploaded)
        # Affiche le brut pour debug
        if raw:
            with st.expander("📄 Texte brut (PDF ou OCR)"):
                st.text(raw)
            df = parse_text_to_df(raw)
        else:
            df = pd.DataFrame(columns=["Référence","Nb de colis","pcs par colis","total","Vérification"])

    st.success("✅ Données extraites")
    st.dataframe(df, use_container_width=True)

    # 5. Export Excel
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="FICHE_RECEPTION")
    out.seek(0)
    st.download_button(
        "📥 Télécharger la FICHE DE RECEPTION",
        data=out,
        file_name="fiche_de_reception.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
