import streamlit as st
import pandas as pd
import requests, io, re
import fitz              # PyMuPDF
from PIL import Image
import base64

# --- Config de la page & style ---
st.set_page_config(page_title="Fiche de réception", layout="wide", page_icon="📋")
st.markdown("""
<style>
  .card { background:white; padding:1.5rem; border-radius:0.5rem;
          box-shadow:0 4px 6px rgba(0,0,0,0.1); margin-bottom:2rem; }
  .section-title { font-size:1.6rem; color:#4A90E2; margin-bottom:0.5rem; }
</style>
""", unsafe_allow_html=True)
st.markdown('<div class="section-title">📥 Documents de réception → FICHE DE RÉCEPTION</div>',
            unsafe_allow_html=True)

# --- Clé Google Vision (via Secrets) ---
GOOGLE_VISION_API_KEY = st.secrets.get("GOOGLE_VISION_API_KEY", "")
if not GOOGLE_VISION_API_KEY:
    st.error("🛑 Ajoute GOOGLE_VISION_API_KEY dans les Secrets.")
    st.stop()
VISION_URL = f"https://vision.googleapis.com/v1/images:annotate?key={GOOGLE_VISION_API_KEY}"

# --- OCR Google Vision pour une image ---
def google_ocr(img_bytes: bytes) -> str:
    """Retourne tout le texte détecté sur l'image."""
    payload = {
        "requests":[
            {
                "image":{"content": base64.b64encode(img_bytes).decode()},
                "features":[{"type":"DOCUMENT_TEXT_DETECTION"}]
            }
        ]
    }
    r = requests.post(VISION_URL, json=payload, timeout=60)
    resp = r.json().get("responses", [{}])[0]
    return resp.get("fullTextAnnotation", {}).get("text", "")

# --- Transforme un PDF en PIL.Image (page unique) ---
def pdf_to_image(pdf_bytes: bytes) -> Image.Image:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pix = doc[0].get_pixmap(dpi=300)  # première page
    return Image.open(io.BytesIO(pix.tobytes("png")))

# --- Découpe une image en 3 colonnes et OCR chacune ---
def ocr_by_columns(img: Image.Image) -> pd.DataFrame:
    w, h = img.size
    # Définition des zones : (x1,y1,x2,y2)
    cols = [
        (0, 0, int(w*0.3), h),           # colonne Réf à 0–30%
        (int(w*0.3), 0, int(w*0.6), h),  # colonne Nb colis 30–60%
        (int(w*0.6), 0, w, h)            # colonne pcs 60–100%
    ]
    texts = []
    for (x1,y1,x2,y2) in cols:
        region = img.crop((x1,y1,x2,y2))
        buf = io.BytesIO()
        region.save(buf, format="PNG")
        texts.append(google_ocr(buf.getvalue()))
    # Nettoyage et alignement
    refs  = [l.strip() for l in texts[0].splitlines() if l.strip()]
    colis = [re.search(r"\d+", l).group(0) for l in texts[1].splitlines() if re.search(r"\d+", l)]
    pcs   = [re.search(r"\d+", l).group(0) for l in texts[2].splitlines() if re.search(r"\d+", l)]
    n = min(len(refs), len(colis), len(pcs))
    rows = []
    for i in range(n):
        c = int(colis[i])
        p = int(pcs[i])
        rows.append({
            "Référence": refs[i],
            "Nb de colis": c,
            "pcs par colis": p,
            "total": c * p,
            "Vérification": ""
        })
    return pd.DataFrame(rows)

# --- Lecture Excel structuré ---
def read_excel(buf_bytes: bytes) -> pd.DataFrame:
    df = pd.read_excel(io.BytesIO(buf_bytes))
    df = df.rename(columns={
        df.columns[0]: "Référence",
        df.columns[1]: "Nb de colis",
        df.columns[2]: "pcs par colis"
    })
    df["total"] = df["Nb de colis"] * df["pcs par colis"]
    df["Vérification"] = ""
    return df[["Référence","Nb de colis","pcs par colis","total","Vérification"]]

# --- Interface utilisateur ---
with st.container():
    st.markdown('<div class="card"><div class="section-title">1️⃣ Import du document</div>', unsafe_allow_html=True)
    uploaded = st.file_uploader("PDF / Image (JPG/PNG) / Excel (.xlsx)", type=["pdf","jpg","jpeg","png","xlsx"])
    st.markdown('</div>', unsafe_allow_html=True)

if uploaded:
    data = uploaded.read()
    ext  = uploaded.name.lower().rsplit(".",1)[-1]
    st.markdown(f"**Fichier :** `{uploaded.name}` — `{len(data)}` bytes")

    # --- 2️⃣ Extraction par zones ---
    with st.container():
        st.markdown('<div class="card"><div class="section-title">2️⃣ Extraction par régions</div>', unsafe_allow_html=True)
        if ext == "xlsx":
            df = read_excel(data)
        else:
            # convertir en image
            img = pdf_to_image(data) if ext == "pdf" else Image.open(io.BytesIO(data))
            st.subheader("📄 Aperçu de la zone Référence")
            st.image(img.crop((0,0,int(img.width*0.3),img.height)), use_column_width=True)
            st.subheader("📄 Aperçu de la zone Nb de colis")
            st.image(img.crop((int(img.width*0.3),0,int(img.width*0.6),img.height)), use_column_width=True)
            st.subheader("📄 Aperçu de la zone pcs par colis")
            st.image(img.crop((int(img.width*0.6),0,img.width,img.height)), use_column_width=True)
            # OCR colonnes
            df = ocr_by_columns(img)
        st.markdown('</div>', unsafe_allow_html=True)

    # --- 3️⃣ Résultats ---
    with st.container():
        st.markdown('<div class="card"><div class="section-title">3️⃣ Résultats</div>', unsafe_allow_html=True)
        st.dataframe(df, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # --- 4️⃣ Export Excel ---
    with st.container():
        st.markdown('<div class="card"><div class="section-title">4️⃣ Export Excel</div>', unsafe_allow_html=True)
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="FICHE_DE_RECEPTION")
        out.seek(0)
        st.download_button(
            label="📥 Télécharger la FICHE DE RÉCEPTION",
            data=out,
            file_name="fiche_de_reception.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
        st.markdown('</div>', unsafe_allow_html=True)
