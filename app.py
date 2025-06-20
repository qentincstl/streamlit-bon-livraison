import streamlit as st
import pandas as pd
import requests, io, re
import fitz               # PyMuPDF
from PIL import Image
import base64

# --- Config de la page & CSS ---
st.set_page_config(page_title="Fiche de réception", layout="wide", page_icon="📋")
st.markdown("""
<style>
  .card { background:white; padding:1.5rem; border-radius:0.5rem;
          box-shadow:0 4px 6px rgba(0,0,0,0.1); margin-bottom:2rem;}
  .section-title { font-size:1.6rem; color:#4A90E2; margin-bottom:0.5rem;}
  .debug { background:#f0f0f0; padding:1rem; border-radius:0.5rem; font-family:monospace;}
</style>
""", unsafe_allow_html=True)
st.markdown('<div class="section-title">📥 Documents de réception → FICHE DE RÉCEPTION</div>',
            unsafe_allow_html=True)

# --- Clé Google Vision (via Secrets) ---
GOOGLE_VISION_API_KEY = st.secrets.get("GOOGLE_VISION_API_KEY", "")
if not GOOGLE_VISION_API_KEY:
    st.error("🛑 Définis `GOOGLE_VISION_API_KEY` dans les Secrets.")
    st.stop()
VISION_URL = f"https://vision.googleapis.com/v1/images:annotate?key={GOOGLE_VISION_API_KEY}"

# --- Fonction OCR Google Vision sur bytes ---
def ocr_google(img_bytes: bytes) -> str:
    payload = {"requests":[{"image":{"content":base64.b64encode(img_bytes).decode()},
                            "features":[{"type":"DOCUMENT_TEXT_DETECTION"}]}]}
    r = requests.post(VISION_URL, json=payload, timeout=60)
    resp = r.json().get("responses", [{}])[0]
    return resp.get("fullTextAnnotation", {}).get("text", "")

# --- Convertir PDF première page en PIL.Image ---
def pdf_to_image(pdf_bytes: bytes) -> Image.Image:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pix = doc[0].get_pixmap(dpi=300)  # page 1
    return Image.open(io.BytesIO(pix.tobytes("png")))

# --- Lecture Excel structuré ---
def read_excel(buf: bytes) -> pd.DataFrame:
    df = pd.read_excel(io.BytesIO(buf))
    df = df.rename(columns={
        df.columns[0]:"Référence", df.columns[1]:"Nb de colis", df.columns[2]:"pcs par colis"
    })
    df["total"] = df["Nb de colis"] * df["pcs par colis"]
    df["Vérification"] = ""
    return df[["Référence","Nb de colis","pcs par colis","total","Vérification"]]

# --- Cropping & OCR par colonnes ---
def ocr_by_columns(img: Image.Image):
    w, h = img.size
    # paramètres de découpage (modifiable)
    ratios = [0.3, 0.6]  # colonnes à 0-30%, 30-60%, 60-100%
    boxes = [
        (0,0,int(w*ratios[0]),h),
        (int(w*ratios[0]),0,int(w*ratios[1]),h),
        (int(w*ratios[1]),0,w,h)
    ]
    region_imgs = [img.crop(b) for b in boxes]
    texts = []
    # OCR de chaque zone + debug visuel
    for i, reg in enumerate(region_imgs):
        st.subheader(f"Zone {i+1} preview")
        st.image(reg, use_column_width=True)
        buf = io.BytesIO(); reg.save(buf, format="PNG")
        txt = ocr_google(buf.getvalue())
        texts.append([l.strip() for l in txt.splitlines() if l.strip()])
        st.markdown(f"**Zone {i+1} OCR brut :**", unsafe_allow_html=True)
        st.markdown(f"<div class='debug'>{txt or '(vide)'}</div>", unsafe_allow_html=True)

    # Alignement par index
    n = min(len(texts[0]), len(texts[1]), len(texts[2]))
    rows = []
    for i in range(n):
        ref = texts[0][i]
        colis = re.findall(r"\d+", texts[1][i])
        pcs   = re.findall(r"\d+", texts[2][i])
        c = int(colis[0]) if colis else None
        p = int(pcs[0])   if pcs   else None
        total = c*p if c is not None and p is not None else None
        rows.append({
            "Référence": ref,
            "Nb de colis": c,
            "pcs par colis": p,
            "total": total,
            "Vérification": ""
        })
    return pd.DataFrame(rows)

# --- Interface ---
with st.container():
    st.markdown('<div class="card"><div class="section-title">1️⃣ Import</div>', unsafe_allow_html=True)
    uploaded = st.file_uploader("PDF/IMG/Excel (.xlsx)", 
                                type=["pdf","jpg","jpeg","png","xlsx"])
    st.markdown('</div>', unsafe_allow_html=True)

if uploaded:
    data = uploaded.read()
    ext  = uploaded.name.lower().rsplit(".",1)[-1]
    st.markdown(f"**Fichier** : `{uploaded.name}` — `{len(data)}` bytes")

    with st.container():
        st.markdown('<div class="card"><div class="section-title">2️⃣ Extraction par zones</div>', 
                    unsafe_allow_html=True)
        if ext=="xlsx":
            df = read_excel(data)
        else:
            img = pdf_to_image(data) if ext=="pdf" else Image.open(io.BytesIO(data))
            df = ocr_by_columns(img)
        st.markdown('</div>', unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="card"><div class="section-title">3️⃣ Résultats</div>', unsafe_allow_html=True)
        st.dataframe(df, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="card"><div class="section-title">4️⃣ Export Excel</div>', unsafe_allow_html=True)
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="FICHE_DE_RECEPTION")
        buf.seek(0)
        st.download_button("📥 Télécharger la FICHE DE RÉCEPTION",
                           data=buf,
                           file_name="fiche_de_reception.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
