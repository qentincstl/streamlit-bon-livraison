import streamlit as st
import pandas as pd
import requests, io, re
import fitz              # PyMuPDF
from PIL import Image
import base64

# --- Page config & style ---
st.set_page_config(page_title="Fiche de réception", layout="wide", page_icon="📋")
st.markdown("""
<style>
  .card { background: white; padding: 1.5rem; border-radius: 0.5rem;
          box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 2rem; }
  .section-title { font-size: 1.6rem; color: #4A90E2; margin-bottom: 0.5rem; }
  .debug { background: #f0f0f0; padding: 1rem; border-radius: 0.5rem; font-family: monospace; }
</style>
""", unsafe_allow_html=True)
st.markdown(
    '<div class="section-title">📥 Documents de réception → FICHE DE RÉCEPTION</div>',
    unsafe_allow_html=True
)

# --- Google Vision API key ---
GOOGLE_VISION_API_KEY = st.secrets.get("GOOGLE_VISION_API_KEY", "")
if not GOOGLE_VISION_API_KEY:
    st.error("🛑 Définissez `GOOGLE_VISION_API_KEY` dans les Secrets de Streamlit Cloud.")
    st.stop()
VISION_URL = f"https://vision.googleapis.com/v1/images:annotate?key={GOOGLE_VISION_API_KEY}"

# --- OCR via Google Vision ---
def ocr_google(img_bytes: bytes) -> str:
    payload = {
        "requests": [{
            "image": {"content": base64.b64encode(img_bytes).decode()},
            "features": [{"type": "DOCUMENT_TEXT_DETECTION"}]
        }]
    }
    resp = requests.post(VISION_URL, json=payload, timeout=60).json()
    return resp.get("responses", [{}])[0].get("fullTextAnnotation", {}).get("text", "")

# --- Convert first PDF page to PIL Image ---
def pdf_to_image(pdf_bytes: bytes) -> Image.Image:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pix = doc[0].get_pixmap(dpi=300)
    return Image.open(io.BytesIO(pix.tobytes("png")))

# --- Read structured Excel input ---
def read_excel(buf: bytes) -> pd.DataFrame:
    df = pd.read_excel(io.BytesIO(buf))
    df = df.rename(columns={
        df.columns[0]: "Référence",
        df.columns[1]: "Nb de colis",
        df.columns[2]: "pcs par colis"
    })
    df["total"] = df["Nb de colis"] * df["pcs par colis"]
    df["Vérification"] = ""
    return df[["Référence","Nb de colis","pcs par colis","total","Vérification"]]

# --- Parsing robust with keywords ---
def parse_robust(raw: str) -> pd.DataFrame:
    refs  = re.findall(r"(?i)(?:ref(?:[ée]rence)?|réf)\s*[:\-]?\s*(\S+)", raw)
    colis = re.findall(r"(?i)(?:colis|nbr\s*colis|nombre\s*de\s*colis)\s*[:\-]?\s*(\d+)", raw)
    pcs   = re.findall(r"(?i)(?:pcs|pi[eè]ces|nbr\s*pi[eè]ces)\s*[:\-]?\s*(\d+)", raw)
    n = min(len(refs), len(colis), len(pcs))
    return pd.DataFrame([{
        "Référence": refs[i],
        "Nb de colis": int(colis[i]),
        "pcs par colis": int(pcs[i]),
        "total": int(colis[i]) * int(pcs[i]),
        "Vérification": ""
    } for i in range(n)])

# --- Fallback parsing: same-line numbers ---
def parse_generic(raw: str) -> pd.DataFrame:
    rows = []
    for line in raw.splitlines():
        nums = re.findall(r"\d+", line)
        if len(nums) >= 3:
            r, c, p = nums[:3]
            rows.append({
                "Référence": r,
                "Nb de colis": int(c),
                "pcs par colis": int(p),
                "total": int(c) * int(p),
                "Vérification": ""
            })
    return pd.DataFrame(rows)

# --- Fallback parsing: groups of 3 lines ---
def parse_sequential(raw: str) -> pd.DataFrame:
    header = re.compile(r"(?i)^(date|nom du client|réf(erence)?|colis|pi[eè]ces)")
    lines = [l.strip() for l in raw.splitlines() if l.strip() and not header.match(l)]
    rows = []
    for i in range(0, len(lines), 3):
        blk = lines[i:i+3]
        if len(blk) == 3 and blk[1].isdigit() and blk[2].isdigit():
            c, p = int(blk[1]), int(blk[2])
            rows.append({
                "Référence": blk[0],
                "Nb de colis": c,
                "pcs par colis": p,
                "total": c * p,
                "Vérification": ""
            })
    return pd.DataFrame(rows)

# --- Orchestrate fallback parsing ---
def parse_with_fallback(raw: str) -> pd.DataFrame:
    df = parse_robust(raw)
    if not df.empty:
        return df
    st.warning("⚠️ Aucun mot-clé détecté → parsing generic…")
    df = parse_generic(raw)
    if not df.empty:
        return df
    st.warning("⚠️ Generic empty → parsing sequential…")
    return parse_sequential(raw)

# --- Crop into columns, OCR, and full-page fallback ---
def ocr_by_columns_with_fallback(img: Image.Image) -> pd.DataFrame:
    w, h = img.size
    cuts = [0.3, 0.6]
    boxes = [
        (0, 0, int(w * cuts[0]), h),
        (int(w * cuts[0]), 0, int(w * cuts[1]), h),
        (int(w * cuts[1]), 0, w, h)
    ]
    zone_texts, counts = [], []
    for idx, (x1, y1, x2, y2) in enumerate(boxes, start=1):
        reg = img.crop((x1, y1, x2, y2))
        buf = io.BytesIO(); reg.save(buf, format="PNG")
        txt = ocr_google(buf.getvalue())
        lines = [l.strip() for l in txt.splitlines() if l.strip()]
        zone_texts.append(lines)
        counts.append(len(lines))
        st.markdown(f"**Zone {idx} OCR brut:**")
        st.markdown(f"<div class='debug'>{txt or '(vide)'}</div>", unsafe_allow_html=True)
    st.write(f"📊 Lignes détectées: Réf={counts[0]}, Colis={counts[1]}, Pièces={counts[2]}")
    n = min(*counts)
    if n > 0:
        return pd.DataFrame([{
            "Référence": zone_texts[0][i],
            "Nb de colis": int(re.findall(r"\d+", zone_texts[1][i])[0]) if re.findall(r"\d+", zone_texts[1][i]) else None,
            "pcs par colis": int(re.findall(r"\d+", zone_texts[2][i])[0]) if re.findall(r"\d+", zone_texts[2][i]) else None,
            "total": None,
            "Vérification": ""
        } for i in range(n)])
    st.warning("⚠️ Aucune ligne alignée ; OCR entier en fallback…")
    buf_full = io.BytesIO(); img.save(buf_full, format="PNG")
    full_txt = ocr_google(buf_full.getvalue())
    st.subheader("🔍 Texte brut complet (OCR entier)")
    st.text_area("", full_txt or "(vide)", height=300)
    return parse_with_fallback(full_txt)

# --- UI ---
with st.container():
    st.markdown('<div class="card"><div class="section-title">1️⃣ Import</div>', unsafe_allow_html=True)
    uploaded = st.file_uploader("PDF / Image / Excel (.xlsx)", type=["pdf","jpg","jpeg","png","xlsx"])
    st.markdown('</div>', unsafe_allow_html=True)

if uploaded:
    data = uploaded.read()
    ext = uploaded.name.lower().rsplit(".", 1)[-1]
    st.markdown(f"**Fichier**: `{uploaded.name}` — `{len(data)}` bytes")

    with st.container():
        st.markdown('<div class="card"><div class="section-title">2️⃣ Extraction par zones</div>', unsafe_allow_html=True)
        if ext == "xlsx":
            df = read_excel(data)
        else:
            img = pdf_to_image(data) if ext == "pdf" else Image.open(io.BytesIO(data))
            df = ocr_by_columns_with_fallback(img)
        st.markdown('</div>', unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="card"><div class="section-title">3️⃣ Résultats</div>', unsafe_allow_html=True)
        st.dataframe(df.fillna(""), use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="card"><div class="section-title">4️⃣ Export</div>', unsafe_allow_html=True)
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            df.to_excel(w, index=False, sheet_name="FICHE_DE_RECEPTION")
        buf.seek(0)
        st.download_button(
            "📥 Télécharger la FICHE DE RÉCEPTION",
            data=buf,
            file_name="fiche_de_reception.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
        st.markdown('</div>', unsafe_allow_html=True)
