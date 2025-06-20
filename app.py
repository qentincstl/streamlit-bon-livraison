import streamlit as st
import pandas as pd
import requests
import io
import re
import fitz  # PyMuPDF

st.set_page_config(page_title="Fiche de réception", layout="wide")
st.title("📥 Documents de réception → FICHE DE RECEPTION")

# -----------------------------------------------------------------------------
# 1) Extraction texte PDF numérique
# -----------------------------------------------------------------------------
def extract_pdf_text(uploaded_file) -> str:
    """Tente d'extraire le texte d'un PDF textuel (non scanné)."""
    try:
        data = uploaded_file.read()
        doc = fitz.open(stream=data, filetype="pdf")
        return "".join(page.get_text() for page in doc)
    except Exception:
        return ""

# -----------------------------------------------------------------------------
# 2) OCR.space avec détection de type MIME
# -----------------------------------------------------------------------------
def ocr_space_file(uploaded_file) -> str:
    """Appelle OCR.space en précisant le bon MIME selon l'extension."""
    api_key = st.secrets.get("OCR_SPACE_API_KEY", "")
    if not api_key:
        st.error("🛑 Clé OCR_SPACE_API_KEY introuvable dans les Secrets Streamlit")
        return ""
    # lecture + détection extension
    uploaded_file.seek(0)
    data = uploaded_file.read()
    ext = uploaded_file.name.lower().split(".")[-1]
    if ext == "pdf":
        mime = "application/pdf"
    elif ext in ("jpg", "jpeg"):
        mime = "image/jpeg"
    elif ext == "png":
        mime = "image/png"
    else:
        st.error(f"🛑 Format non supporté : .{ext}")
        return ""
    files = {"file": (uploaded_file.name, data, mime)}
    payload = {"apikey": api_key, "language": "fre", "isOverlayRequired": False}

    resp = requests.post(
        "https://api.ocr.space/parse/image",
        files=files,
        data=payload,
        timeout=60
    )
    if resp.status_code != 200:
        st.error(f"🛑 Erreur HTTP {resp.status_code} depuis OCR.space")
        st.text(resp.text)
        return ""
    result = resp.json()
    if result.get("IsErroredOnProcessing"):
        msg = result.get("ErrorMessage", ["Erreur inconnue"])[0]
        st.error(f"🛑 OCR.space a retourné une erreur : {msg}")
        return ""
    return "\n".join(p["ParsedText"] for p in result.get("ParsedResults", []))

# -----------------------------------------------------------------------------
# 3) Parsing du texte brut en DataFrame
# -----------------------------------------------------------------------------
def parse_text_to_df(raw: str) -> pd.DataFrame:
    """
    Transforme le texte OCR ou PDF brut en DataFrame avec colonnes :
    EAN, Désignation produits, Nb de colis, pcs par colis, total, Vérification
    """
    rows = []
    for line in raw.splitlines():
        line = line.strip()
        # regex qui détecte : EAN (8–13 chiffres), nom, nb_colis, pcs_colis
        m = re.search(r"(\d{8,13}).*?([A-Za-zÀ-ÖØ-öø-ÿ0-9 \-]+?)\s+(\d+)\s+(\d+)$", line)
        if m:
            ean, name, colis, pcs = m.groups()
            colis_i, pcs_i = int(colis), int(pcs)
            rows.append({
                "EAN": ean,
                "Désignation produits": name.strip(),
                "Nb de colis": colis_i,
                "pcs par colis": pcs_i,
                "total": colis_i * pcs_i,
                "Vérification": ""
            })
    if not rows:
        st.warning("⚠️ Aucune ligne valide détectée via OCR/PDF textuel.")
    return pd.DataFrame(rows)

# -----------------------------------------------------------------------------
# 4) Lecture d'un Excel d'entrée
# -----------------------------------------------------------------------------
def read_excel_to_df(buffer: io.BytesIO) -> pd.DataFrame:
    """Lit un Excel existant et le reformate/nomme ses colonnes."""
    df = pd.read_excel(buffer)
    df = df.rename(columns={
        df.columns[0]: "EAN",
        df.columns[1]: "Désignation produits",
        df.columns[2]: "Nb de colis",
        df.columns[3]: "pcs par colis"
    })
    df["total"] = df["Nb de colis"] * df["pcs par colis"]
    df["Vérification"] = ""
    return df[[
        "EAN", "Désignation produits",
        "Nb de colis", "pcs par colis",
        "total", "Vérification"
    ]]

# -----------------------------------------------------------------------------
# 5) Upload & traitement global
# -----------------------------------------------------------------------------
uploaded = st.file_uploader(
    "📂 Déposez un PDF, une image (JPG/PNG) ou un fichier Excel",
    type=["pdf", "jpg", "jpeg", "png", "xlsx"]
)

if uploaded:
    ext = uploaded.name.lower().split(".")[-1]
    # si Excel
    if ext == "xlsx":
        df = read_excel_to_df(io.BytesIO(uploaded.read()))
    else:
        # PDF textuel d'abord
        raw_text = ""
        if ext == "pdf":
            raw_text = extract_pdf_text(uploaded)
        # sinon OCR cloud
        if not raw_text:
            raw_text = ocr_space_file(uploaded)
        # affichage du texte brut pour debug
        if raw_text:
            with st.expander("📄 Voir le texte brut (PDF/OCR)"):
                st.text(raw_text)
            df = parse_text_to_df(raw_text)
        else:
            df = pd.DataFrame(columns=[
                "EAN", "Désignation produits",
                "Nb de colis", "pcs par colis",
                "total", "Vérification"
            ])

    st.success("✅ Données extraites")
    st.dataframe(df, use_container_width=True)

    # Génère le fichier Excel de sortie
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="FICHE DE RECEPTION")
    output.seek(0)
    st.download_button(
        label="📥 Télécharger la FICHE DE RECEPTION",
        data=output,
        file_name="fiche_de_reception.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
