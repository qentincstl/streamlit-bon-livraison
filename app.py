import streamlit as st
import pandas as pd
import requests, io, re
import fitz              # PyMuPDF
import base64

# --- Configuration de la page et style ---
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

# --- Clé Google Vision via Secrets UI ---
GOOGLE_VISION_API_KEY = st.secrets.get("GOOGLE_VISION_API_KEY", "")
if not GOOGLE_VISION_API_KEY:
    st.error("🛑 Définis `GOOGLE_VISION_API_KEY` dans les Secrets de Streamlit Cloud.")
    st.stop()
VISION_URL = f"https://vision.googleapis.com/v1/images:annotate?key={GOOGLE_VISION_API_KEY}"

# --- OCR Google Vision pour une image ---
def google_ocr_image(img_bytes: bytes) -> str:
    content = base64.b64encode(img_bytes).decode()
    body = {
      "requests":[
        {
          "image":{"content": content},
          "features":[{"type":"DOCUMENT_TEXT_DETECTION"}]
        }
      ]
    }
    resp = requests.post(VISION_URL, json=body, timeout=60)
    data = resp.json()
    return "\n".join(r.get("fullTextAnnotation",{}).get("text","")
                     for r in data.get("responses",[]))

# --- Extraction texte PDF natif (si possible) ---
def extract_pdf_text(pdf_bytes: bytes) -> str:
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        return "\n".join(page.get_text() for page in doc)
    except:
        return ""

# --- OCR page par page pour PDF scanné ---
def google_ocr_pdf(pdf_bytes: bytes) -> str:
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except:
        return ""
    full = ""
    for page in doc:
        pix = page.get_pixmap(dpi=300)
        png = pix.tobytes("png")
        full += google_ocr_image(png) + "\n"
    return full

# --- Parsing variant keywords pour ref/colis/pcs ---
def parse_robust(raw: str) -> pd.DataFrame:
    refs   = re.findall(r"(?i)(?:ref(?:[ée]rence)?|réf)\s*[:\-]?\s*(\S+)", raw)
    colis  = re.findall(r"(?i)(?:nombre\s*de\s*colis|nbr\s*colis|colis)\s*[:\-]?\s*(\d+)", raw)
    pcs    = re.findall(r"(?i)(?:nombre\s*de\s*pi[eè]ces|pcs(?:\s*par\s*colis)?|pi[eè]ce?s?)\s*[:\-]?\s*(\d+)", raw)
    n = min(len(refs), len(colis), len(pcs))
    rows = []
    for i in range(n):
        c, p = int(colis[i]), int(pcs[i])
        rows.append({
            "Référence": refs[i],
            "Nb de colis": c,
            "pcs par colis": p,
            "total": c * p,
            "Vérification": ""
        })
    return pd.DataFrame(rows)

# --- Parsing générique : 3 nombres sur une seule ligne ---
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
                "total": int(c)*int(p),
                "Vérification": ""
            })
    return pd.DataFrame(rows)

# --- Parsing séquentiel : une valeur par ligne regroupée par 3 ---
def parse_sequential(raw: str) -> pd.DataFrame:
    # On filtre hors entêtes
    lines = [l.strip() for l in raw.splitlines()
             if l.strip() and not re.match(
                 r"(?i)^(date|nom du client|référence|nombre de colis|nombre de pièces)", l)]
    rows = []
    for i in range(0, len(lines), 3):
        chunk = lines[i:i+3]
        if len(chunk) == 3:
            ref, colis, pcs = chunk
            try:
                c, p = int(colis), int(pcs)
                rows.append({
                    "Référence": ref,
                    "Nb de colis": c,
                    "pcs par colis": p,
                    "total": c * p,
                    "Vérification": ""
                })
            except:
                continue
    return pd.DataFrame(rows)

# --- Fallback orchestration ---
def parse_with_fallback(raw: str) -> pd.DataFrame:
    df = parse_robust(raw)
    if not df.empty:
        return df
    st.warning("⚠️ Pas de mots-clés, fallback générique.")
    df = parse_generic(raw)
    if not df.empty:
        return df
    st.warning("⚠️ Fallback générique vide, fallback séquentiel.")
    df = parse_sequential(raw)
    if df.empty:
        st.warning("⚠️ Même le séquentiel n’a rien détecté.")
    return df

# --- Lecture Excel structuré ---
def read_excel_bytes(x: bytes) -> pd.DataFrame:
    try:
        df = pd.read_excel(io.BytesIO(x))
        df = df.rename(columns={
            df.columns[0]: "Référence",
            df.columns[1]: "Nb de colis",
            df.columns[2]: "pcs par colis"
        })
        df["total"] = df["Nb de colis"] * df["pcs par colis"]
        df["Vérification"] = ""
        return df[[
            "Référence","Nb de colis","pcs par colis","total","Vérification"
        ]]
    except Exception as e:
        st.error(f"❌ Erreur lecture Excel : {e}")
        return pd.DataFrame(columns=[
            "Référence","Nb de colis","pcs par colis","total","Vérification"
        ])

# --- 1️⃣ Import du document ---
with st.container():
    st.markdown('<div class="card"><div class="section-title">1️⃣ Import</div>', unsafe_allow_html=True)
    uploaded = st.file_uploader(
        "PDF / Image (JPG/PNG) / Excel (.xlsx)",
        type=["pdf","jpg","jpeg","png","xlsx"]
    )
    st.markdown('</div>', unsafe_allow_html=True)

if uploaded:
    data = uploaded.read()
    ext  = uploaded.name.lower().rsplit(".",1)[-1]
    st.markdown(f"**Fichier** : `{uploaded.name}` — `{len(data)}` bytes")

    # --- 2️⃣ Extraction / OCR ---
    with st.container():
        st.markdown('<div class="card"><div class="section-title">2️⃣ Extraction du texte</div>', unsafe_allow_html=True)
        if ext == "xlsx":
            raw = None
        else:
            raw = extract_pdf_text(data) if ext == "pdf" else ""
            if not raw.strip():
                raw = google_ocr_pdf(data) if ext == "pdf" else google_ocr_image(data)
        st.subheader("📄 Texte brut extrait")
        st.text_area("", raw or "(vide)", height=200)
        df = read_excel_bytes(data) if ext=="xlsx" else parse_with_fallback(raw or "")
        st.markdown('</div>', unsafe_allow_html=True)

    # --- 3️⃣ Résultats ---
    with st.container():
        st.markdown('<div class="card"><div class="section-title">3️⃣ Résultats</div>', unsafe_allow_html=True)
        st.dataframe(df, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # --- 4️⃣ Export Excel ---
    with st.container():
        st.markdown('<div class="card"><div class="section-title">4️⃣ Export Excel</div>', unsafe_allow_html=True)
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            df.to_excel(w, index=False, sheet_name="FICHE_DE_RECEPTION")
        buf.seek(0)
        st.download_button("📥 Télécharger la FICHE DE RÉCEPTION",
                           data=buf,
                           file_name="fiche_de_reception.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
