# app.py
import streamlit as st
import pandas as pd
import requests
import io
import re
import fitz                                   # PyMuPDF
from PIL import Image

st.set_page_config(page_title="Fiche de réception", layout="wide")
st.title("📥 Documents de réception → FICHE DE RÉCEPTION")

# Ta clé OCR.space (via Secrets Cloud)
OCR_KEY = st.secrets["OCR_SPACE_API_KEY"]

def ocr_image_bytes(img_bytes: bytes) -> str:
    """Envoie une image PNG à OCR.space et renvoie le texte brut."""
    resp = requests.post(
        "https://api.ocr.space/parse/image",
        files={"file": ("page.png", img_bytes, "image/png")},
        data={"apikey": OCR_KEY, "language":"fre", "isOverlayRequired": False},
        timeout=60
    )
    j = resp.json()
    if j.get("IsErroredOnProcessing"):
        st.error("🛑 OCR.space error: " + str(j["ErrorMessage"]))
        return ""
    return "\n".join(p["ParsedText"] for p in j.get("ParsedResults", []))

def ocr_pdf(pdf_bytes: bytes) -> str:
    """Convertit chaque page du PDF en image, puis OCR dessus."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    full_text = ""
    for page in doc:
        pix = page.get_pixmap(dpi=300)
        png = pix.tobytes("png")
        full_text += ocr_image_bytes(png) + "\n"
    return full_text

def parse_fixed_table(raw: str) -> pd.DataFrame:
    """
    Pour chaque ligne contenant au moins 3 nombres,
    on prend les 3 premiers comme Réf, colis, pcs.
    """
    rows = []
    for line in raw.splitlines():
        nums = re.findall(r"\d+", line)
        if len(nums) >= 3:
            ref, colis, pcs = nums[0], nums[1], nums[2]
            rows.append({
                "Référence": ref,
                "Nb de colis": int(colis),
                "pcs par colis": int(pcs),
                "total": int(colis) * int(pcs),
                "Vérification": ""
            })
    if not rows:
        st.warning("⚠️ Aucune ligne valide détectée.")
    return pd.DataFrame(rows)

def read_excel(buf: io.BytesIO) -> pd.DataFrame:
    """Lit un .xlsx déjà structuré et calcule la colonne total."""
    df = pd.read_excel(buf)
    df = df.rename(columns={
        df.columns[0]: "Référence",
        df.columns[1]: "Nb de colis",
        df.columns[2]: "pcs par colis"
    })
    df["total"] = df["Nb de colis"] * df["pcs par colis"]
    df["Vérification"] = ""
    return df[[
        "Référence", "Nb de colis", "pcs par colis",
        "total", "Vérification"
    ]]

# --- Interface utilisateur ---
uploaded = st.file_uploader(
    "📂 Déposez un PDF manuscrit, une image (JPG/PNG) ou un fichier Excel (.xlsx)",
    type=["pdf","jpg","jpeg","png","xlsx"]
)

if uploaded:
    ext = uploaded.name.lower().split(".")[-1]
    # Cas Excel déjà structuré
    if ext == "xlsx":
        df = read_excel(io.BytesIO(uploaded.read()))
    else:
        data = uploaded.read()
        # OCR du PDF/scans
        if ext == "pdf":
            raw = ocr_pdf(data)
        else:
            raw = ocr_image_bytes(data)
        # Affichage du texte brut pour contrôle
        with st.expander("📄 Texte brut OCR"):
            st.text(raw)
        # Parsing fixe
        df = parse_fixed_table(raw)

    st.success("✅ Données extraites")
    st.dataframe(df, use_container_width=True)

    # Export Excel
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="FICHE_DE_RECEPTION")
    out.seek(0)
    st.download_button(
        "📥 Télécharger la FICHE DE RECEPTION",
        data=out,
        file_name="fiche_de_reception.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
