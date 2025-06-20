import streamlit as st
import pandas as pd
import requests, io, re
import fitz              # PyMuPDF
from PIL import Image

# --- Config de la page ---
st.set_page_config(page_title="Fiche de réception", layout="wide")
st.title("📥 Documents de réception → FICHE DE RÉCEPTION")

# --- Clé OCR.space (via Secrets UI) ---
OCR_KEY = st.secrets.get("OCR_SPACE_API_KEY", "")
if not OCR_KEY:
    st.error("🛑 Veuillez définir OCR_SPACE_API_KEY dans les Secrets de Streamlit Cloud.")
    st.stop()

# --- Fonctions utilitaires ---

def extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extraction native du texte si PDF contient du texte."""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        return "\n".join(page.get_text() for page in doc)
    except Exception:
        return ""

def ocr_image_bytes(img_bytes: bytes) -> str:
    """Envoie une image PNG à OCR.space et retourne le texte."""
    resp = requests.post(
        "https://api.ocr.space/parse/image",
        files={ "file": ("img.png", img_bytes, "image/png") },
        data={ "apikey": OCR_KEY, "language":"fre", "isOverlayRequired": False },
        timeout=60
    )
    j = resp.json()
    if j.get("IsErroredOnProcessing"):
        return ""
    return "\n".join(p["ParsedText"] for p in j.get("ParsedResults", []))

def ocr_pdf_bytes(pdf_bytes: bytes) -> str:
    """Convertit chaque page du PDF en image et fait l'OCR dessus."""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        return ""
    full = ""
    for page in doc:
        pix = page.get_pixmap(dpi=300)
        png = pix.tobytes("png")
        full += ocr_image_bytes(png) + "\n"
    return full

def parse_fixed(raw: str) -> pd.DataFrame:
    """Parse les lignes contenant ≥3 nombres en Réf / Nb colis / pcs, calcule total."""
    rows = []
    for line in raw.splitlines():
        nums = re.findall(r"\d+", line)
        if len(nums) >= 3:
            ref, colis, pcs = nums[:3]
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

def read_excel_bytes(xl_bytes: bytes) -> pd.DataFrame:
    """Lit un .xlsx structuré et calcule automatiquement la colonne total."""
    try:
        df = pd.read_excel(io.BytesIO(xl_bytes))
        df = df.rename(columns={
            df.columns[0]: "Référence",
            df.columns[1]: "Nb de colis",
            df.columns[2]: "pcs par colis"
        })
        df["total"] = df["Nb de colis"] * df["pcs par colis"]
        df["Vérification"] = ""
        return df[[
            "Référence","Nb de colis","pcs par colis",
            "total","Vérification"
        ]]
    except Exception as e:
        st.error(f"❌ Erreur lecture Excel : {e}")
        return pd.DataFrame(columns=[
            "Référence","Nb de colis","pcs par colis","total","Vérification"
        ])

# --- Interface utilisateur ---
uploaded = st.file_uploader(
    "📂 Déposez un PDF (manuscrit ou numérique), une image (JPG/PNG) ou un Excel (.xlsx)",
    type=["pdf","jpg","jpeg","png","xlsx"]
)

if uploaded:
    data = uploaded.read()
    ext = uploaded.name.lower().split(".")[-1]
    st.markdown(f"**Fichier** : `{uploaded.name}` — `{len(data)} bytes`")

    if ext == "xlsx":
        df = read_excel_bytes(data)
    else:
        # PDF numérique ?
        raw = extract_pdf_text(data) if ext == "pdf" else ""
        # Sinon OCR par images
        if not raw.strip():
            raw = ocr_pdf_bytes(data) if ext == "pdf" else ocr_image_bytes(data)
        # Affiche le brut pour vérif
        with st.expander("📄 Texte brut extrait"):
            st.text(raw if raw else "(vide)")
        # Parse et tableau
        df = parse_fixed(raw)

    st.success("✅ Extraction terminée")
    st.dataframe(df, use_container_width=True)

    # Génère et propose le téléchargement Excel
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="FICHE_DE_RECEPTION")
    buf.seek(0)
    st.download_button(
        "📥 Télécharger la FICHE DE RÉCEPTION",
        data=buf,
        file_name="fiche_de_reception.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
