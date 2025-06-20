import streamlit as st
import pandas as pd
import requests, io, re
import fitz  # PyMuPDF

st.set_page_config(page_title="DEBUG Fiche Réception", layout="wide")
st.title("🛠️ DEBUG Documents de réception → FICHE DE RÉCEPTION")

# 1) Extraction texte PDF numérique
def extract_pdf_text(uploaded_file) -> str:
    st.info("🔍 [DEBUG] extract_pdf_text() appelé")
    try:
        uploaded_file.seek(0)
        data = uploaded_file.read()
        st.write(f"[DEBUG] Taille des bytes PDF textuel : {len(data)}")
        doc = fitz.open(stream=data, filetype="pdf")
        txt = "\n".join(page.get_text() for page in doc)
        st.write(f"[DEBUG] Longueur du texte PDF brut : {len(txt)}")
        return txt
    except Exception as e:
        st.error(f"[DEBUG] extract_pdf_text() ERREUR: {e}")
        return ""

# 2) OCR.space avec MIME correct et debug brut
def ocr_space_file(uploaded_file) -> str:
    st.info("🔍 [DEBUG] ocr_space_file() appelé")
    api_key = st.secrets.get("OCR_SPACE_API_KEY", "")
    st.write(f"[DEBUG] Clé OCR_SPACE_API_KEY présente: {bool(api_key)}")
    if not api_key:
        st.error("🛑 Clé OCR_SPACE_API_KEY manquante dans les Secrets")
        return ""
    uploaded_file.seek(0)
    data = uploaded_file.read()
    st.write(f"[DEBUG] Taille des bytes pour OCR.space : {len(data)}")
    ext = uploaded_file.name.lower().split(".")[-1]
    st.write(f"[DEBUG] Extension détectée pour OCR.space : .{ext}")
    mime = {
        "pdf": "application/pdf",
        "jpg": "image/jpeg", "jpeg": "image/jpeg",
        "png": "image/png"
    }.get(ext)
    if not mime:
        st.error(f"🛑 Format non supporté: .{ext}")
        return ""

    files = {"file": (uploaded_file.name, data, mime)}
    payload = {"apikey": api_key, "language": "fre", "isOverlayRequired": False}

    resp = requests.post(
        "https://api.ocr.space/parse/image",
        files=files,
        data=payload,
        timeout=60
    )
    st.write("📋 [DEBUG] OCR.space raw response:", resp.text)

    if resp.status_code != 200:
        st.error(f"🛑 Erreur HTTP {resp.status_code} depuis OCR.space")
        st.text(resp.text)
        return ""
    try:
        j = resp.json()
    except Exception as e:
        st.error(f"🛑 Impossible de parser le JSON OCR.space : {e}")
        return ""
    st.write("🔑 [DEBUG] OCR.space JSON keys:", list(j.keys()))
    st.write("✳️ [DEBUG] ParsedResults:", j.get("ParsedResults"))
    if j.get("IsErroredOnProcessing"):
        st.error(f"🛑 OCR.space a retourné une erreur: {j.get('ErrorMessage')}")
        return ""
    texts = [p.get("ParsedText","") for p in j.get("ParsedResults",[])]
    full = "\n".join(texts)
    st.write(f"✏️ [DEBUG] Texte OCR.length = {len(full)} caractères")
    return full

# 3) Parsing très souple : 3+ nombres
def parse_text_to_df(raw: str) -> pd.DataFrame:
    st.info("🔍 [DEBUG] parse_text_to_df() appelé")
    rows = []
    for line in raw.splitlines():
        nums = re.findall(r"\d+", line)
        if len(nums) >= 3:
            ref, colis, pcs = nums[0], nums[1], nums[2]
            rows.append({
                "Référence": ref,
                "Nb de colis": int(colis),
                "pcs par colis": int(pcs),
                "total": int(colis)*int(pcs),
                "Vérification": ""
            })
    st.write(f"[DEBUG] Lignes parsées: {len(rows)}")
    return pd.DataFrame(rows)

# 4) Lecture Excel
def read_excel_to_df(buf: io.BytesIO) -> pd.DataFrame:
    st.info("🔍 [DEBUG] read_excel_to_df() appelé")
    df = pd.read_excel(buf)
    st.write(f"[DEBUG] Colonnes Excel entrantes: {list(df.columns)}")
    df = df.rename(columns={
        df.columns[0]:"Référence",
        df.columns[1]:"Nb de colis",
        df.columns[2]:"pcs par colis"
    })
    df["total"] = df["Nb de colis"] * df["pcs par colis"]
    df["Vérification"] = ""
    return df[["Référence","Nb de colis","pcs par colis","total","Vérification"]]

# Interface
uploaded = st.file_uploader(
    "📂 Déposez un PDF, JPG/PNG ou .xlsx",
    type=["pdf","jpg","jpeg","png","xlsx"]
)

if uploaded:
    ext = uploaded.name.lower().split(".")[-1]
    st.write(f"[DEBUG] Fichier uploadé: {uploaded.name}")
    if ext == "xlsx":
        df = read_excel_to_df(io.BytesIO(uploaded.read()))
    else:
        raw = ""
        if ext == "pdf":
            raw = extract_pdf_text(uploaded)
        if not raw.strip():
            raw = ocr_space_file(uploaded)
        if raw:
            with st.expander("📄 TEXTE BRUT (PDF/OCR)"):
                st.text(raw)
            df = parse_text_to_df(raw)
        else:
            st.error("❌ Aucune donnée brute récupérée.")
            df = pd.DataFrame(columns=["Référence","Nb de colis","pcs par colis","total","Vérification"])
    st.success("✅ Données extraites")
    st.dataframe(df, use_container_width=True)
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="FICHE")
    out.seek(0)
    st.download_button("📥 Télécharger Excel", data=out,
                       file_name="fiche_reception.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
