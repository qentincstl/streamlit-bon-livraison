import streamlit as st
import pandas as pd
import io, re
import fitz                 # PyMuPDF
from PIL import Image
import easyocr

# --- 0️⃣ Configuration page & style ---
st.set_page_config(page_title="Fiche de réception", layout="wide", page_icon="📋")
st.markdown("""
<style>
  .card { background:white; padding:1.5rem; border-radius:0.5rem;
          box-shadow:0 4px 6px rgba(0,0,0,0.1); margin-bottom:2rem; }
  .section-title { font-size:1.6rem; color:#4A90E2; margin-bottom:0.5rem; }
  .debug { background:#f0f0f0; padding:1rem; border-radius:0.5rem; font-family:monospace; }
</style>
""", unsafe_allow_html=True)
st.markdown(
    '<div class="section-title">📥 Documents de réception → FICHE DE RÉCEPTION</div>',
    unsafe_allow_html=True
)

# --- 1️⃣ Initialise EasyOCR reader (français) ---
@st.cache_resource
def get_reader():
    return easyocr.Reader(["fr"], gpu=False)
reader = get_reader()

# --- 2️⃣ Utilitaires pour convertir PDF→Image ---
def pdf_to_image(pdf_bytes: bytes) -> Image.Image:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pix = doc[0].get_pixmap(dpi=300)
    return Image.open(io.BytesIO(pix.tobytes("png")))

# --- 3️⃣ OCR par régions (3 colonnes) ---
def ocr_by_columns_eo(img: Image.Image) -> pd.DataFrame:
    w,h = img.size
    cuts = [0.3, 0.6]
    boxes = [
        (0, 0, int(w*cuts[0]), h),
        (int(w*cuts[0]), 0, int(w*cuts[1]), h),
        (int(w*cuts[1]), 0, w, h)
    ]
    zones = ["Référence","Nb de colis","pcs par colis"]
    all_lines = {}
    counts = {}
    for name, (x1,y1,x2,y2) in zip(zones, boxes):
        crop = img.crop((x1,y1,x2,y2))
        # debug : affichage mini-aperçu
        st.subheader(f"Aperçu zone « {name} »")
        st.image(crop, use_column_width=True)
        # OCR EasyOCR
        result = reader.readtext(
            np.array(crop.convert("RGB")), 
            detail=0,              # juste le texte
            paragraph=True
        )
        lines = [r.strip() for r in result if r.strip()]
        all_lines[name] = lines
        counts[name] = len(lines)
        st.markdown(f"**Zone {name} — {len(lines)} lignes détectées**")
        st.markdown(f"<div class='debug'>{chr(10).join(lines)}</div>", unsafe_allow_html=True)

    #  alignement
    n = min(counts.values())
    if n > 0:
        rows = []
        for i in range(n):
            ref = all_lines["Référence"][i]
            colis = re.findall(r"\d+", all_lines["Nb de colis"][i])
            pcs   = re.findall(r"\d+", all_lines["pcs par colis"][i])
            c = int(colis[0]) if colis else None
            p = int(pcs[0])   if pcs   else None
            rows.append({
                "Référence": ref,
                "Nb de colis": c,
                "pcs par colis": p,
                "total": c*p if c is not None and p is not None else None,
                "Vérification": ""
            })
        return pd.DataFrame(rows)
    # fallback texte brut
    st.warning("⚠️ Pas d’alignement, OCR page entière en fallback…")
    full_text = "\n".join(
        reader.readtext(
            np.array(img.convert("RGB")), detail=0, paragraph=True
        )
    )
    st.subheader("🔍 Texte brut complet")
    st.text_area("", full_text or "(vide)", height=300)
    return parse_with_fallback(full_text)

# --- 4️⃣ Lecture Excel structuré ---
def read_excel(buf: bytes) -> pd.DataFrame:
    df = pd.read_excel(io.BytesIO(buf))
    df = df.rename(columns={
        df.columns[0]:"Référence",
        df.columns[1]:"Nb de colis",
        df.columns[2]:"pcs par colis"
    })
    df["total"] = df["Nb de colis"] * df["pcs par colis"]
    df["Vérification"] = ""
    return df[["Référence","Nb de colis","pcs par colis","total","Vérification"]]

# --- 5️⃣ Parsers fallback (robust / generic / sequential) ---
def parse_robust(raw: str) -> pd.DataFrame:
    # même code que tu avais pour mots-clés…
    # …
    return df

def parse_generic(raw: str) -> pd.DataFrame:
    # …
    return df

def parse_sequential(raw: str) -> pd.DataFrame:
    # …
    return df

def parse_with_fallback(raw: str) -> pd.DataFrame:
    df = parse_robust(raw)
    if not df.empty: return df
    df = parse_generic(raw)
    if not df.empty: return df
    return parse_sequential(raw)

# --- 6️⃣ Interface & workflow ---
with st.container():
    st.markdown('<div class="card"><div class="section-title">1️⃣ Import</div>', unsafe_allow_html=True)
    uploaded = st.file_uploader("PDF/Image/Excel (.xlsx)", type=["pdf","jpg","jpeg","png","xlsx"])
    st.markdown('</div>', unsafe_allow_html=True)

if uploaded:
    data = uploaded.read()
    ext = uploaded.name.lower().rsplit(".",1)[-1]
    st.markdown(f"**Fichier**: `{uploaded.name}` — `{len(data)}` bytes")

    with st.container():
        st.markdown('<div class="card"><div class="section-title">2️⃣ Extraction</div>', unsafe_allow_html=True)
        if ext == "xlsx":
            df = read_excel(data)
        else:
            img = pdf_to_image(data) if ext=="pdf" else Image.open(io.BytesIO(data))
            df = ocr_by_columns_eo(img)
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
        st.download_button("📥 Télécharger Excel", data=buf,
                           file_name="fiche_de_reception.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
