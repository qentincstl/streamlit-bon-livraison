import streamlit as st
import pandas as pd
import requests, io, re
import fitz              # PyMuPDF
from PIL import Image

st.set_page_config(page_title="Fiche réception robuste", layout="wide")
st.title("📥 Documents → FICHE DE RÉCEPTION")

# Clé OCR.space depuis les Secrets
OCR_KEY = st.secrets.get("OCR_SPACE_API_KEY", "")
if not OCR_KEY:
    st.error("🛑 OCR_SPACE_API_KEY manquante dans les Secrets.")
    st.stop()

def ocr_image_bytes(img_bytes: bytes) -> str:
    try:
        r = requests.post(
            "https://api.ocr.space/parse/image",
            files={ "file": ("img.png", img_bytes, "image/png") },
            data={ "apikey": OCR_KEY, "language":"fre", "isOverlayRequired": False },
            timeout=60
        )
        j = r.json()
        if j.get("IsErroredOnProcessing"):
            return ""
        return "\n".join(p["ParsedText"] for p in j.get("ParsedResults", []))
    except Exception as e:
        st.error(f"❌ Erreur OCR.image : {e}")
        return ""

def ocr_pdf_bytes(pdf_bytes: bytes) -> str:
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        full = ""
        for page in doc:
            pix = page.get_pixmap(dpi=300)
            png = pix.tobytes("png")
            full += ocr_image_bytes(png) + "\n"
        return full
    except Exception as e:
        st.error(f"❌ Erreur OCR.pdf : {e}")
        return ""

def parse_fixed(raw: str) -> pd.DataFrame:
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
    try:
        df = pd.read_excel(io.BytesIO(xl_bytes))
        df = df.rename(columns={
            df.columns[0]:"Référence",
            df.columns[1]:"Nb de colis",
            df.columns[2]:"pcs par colis"
        })
        df["total"] = df["Nb de colis"] * df["pcs par colis"]
        df["Vérification"] = ""
        return df[["Référence","Nb de colis","pcs par colis","total","Vérification"]]
    except Exception as e:
        st.error(f"❌ Erreur lecture Excel : {e}")
        return pd.DataFrame(columns=["Référence","Nb de colis","pcs par colis","total","Vérification"])

# --- Interface ---
uploaded = st.file_uploader(
    "Déposez PDF / Image (JPG/PNG) / Excel (.xlsx)",
    type=["pdf","jpg","jpeg","png","xlsx"]
)

if uploaded:
    # Lis UNE fois les bytes
    data = uploaded.read()
    ext = uploaded.name.lower().split(".")[-1]
    st.write(f"📄 Fichier : {uploaded.name} ({len(data)} bytes)")

    # Cas Excel
    if ext == "xlsx":
        df = read_excel_bytes(data)

    else:
        # OCR selon type
        if ext == "pdf":
            raw = ocr_pdf_bytes(data)
        else:
            raw = ocr_image_bytes(data)

        # Affiche le texte brut pour contrôle
        with st.expander("📄 Texte brut OCR"):
            st.text(raw if raw else "(vide)")

        df = parse_fixed(raw)

    st.success("✅ Extraction terminée")
    st.dataframe(df, use_container_width=True)

    # Export Excel
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="FICHE_DE_RECEPTION")
    buf.seek(0)
    st.download_button(
        "📥 Télécharger Excel",
        data=buf,
        file_name="fiche_de_reception.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
