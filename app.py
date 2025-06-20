import streamlit as st
import pandas as pd
import requests, io, re
import fitz            # PyMuPDF
import base64

# --- Configuration page & CSS ---
st.set_page_config(page_title="Fiche de réception", layout="wide", page_icon="📋")
st.markdown("""
<style>
  .card { background:white; padding:1.5rem; border-radius:0.5rem;
          box-shadow:0 4px 6px rgba(0,0,0,0.1); margin-bottom:2rem; }
  .section-title { font-size:1.6rem; color:#4A90E2; margin-bottom:0.5rem; }
</style>
""", unsafe_allow_html=True)
st.markdown(
    '<div class="section-title">📥 Documents de réception → FICHE DE RÉCEPTION</div>',
    unsafe_allow_html=True
)

# --- Clé Google Vision (via Secrets) ---
GOOGLE_VISION_API_KEY = st.secrets.get("GOOGLE_VISION_API_KEY", "")
if not GOOGLE_VISION_API_KEY:
    st.error("🛑 Ajoute ta clé GOOGLE_VISION_API_KEY dans les Secrets.")
    st.stop()
VISION_URL = f"https://vision.googleapis.com/v1/images:annotate?key={GOOGLE_VISION_API_KEY}"

# --- OCR Google Vision pour images ---
def google_ocr_image(img_bytes: bytes) -> str:
    payload = {"requests":[{"image":{"content":base64.b64encode(img_bytes).decode()},
                            "features":[{"type":"DOCUMENT_TEXT_DETECTION"}]}]}
    r = requests.post(VISION_URL, json=payload, timeout=60)
    resp = r.json().get("responses", [{}])[0]
    return resp.get("fullTextAnnotation", {}).get("text", "")

# --- Extraction texte natif PDF ---
def extract_pdf_text(pdf_bytes: bytes) -> str:
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        return "\n".join(page.get_text() for page in doc)
    except:
        return ""

# --- OCR page-par-page PDF scanné ---
def google_ocr_pdf(pdf_bytes: bytes) -> str:
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except:
        return ""
    out = ""
    for page in doc:
        pix = page.get_pixmap(dpi=300)
        out += google_ocr_image(pix.tobytes("png")) + "\n"
    return out

# --- Parsing par mots-clés ultra-variantes ---
def parse_keywords(raw: str) -> pd.DataFrame:
    # Référence : ref, référence, réf, sku, art., art, code, item, no, n°, n°
    ref_pattern = r"(?i)\b(?:ref(?:[ée]rence)?|réf|sku|art(?:\.|icle)?|code|item|n[o°])\b\s*[:\-]?\s*(\w+)"
    # Colis : nombre de colis, nbr colis, nbre colis, nb colis, n° colis, qté colis, quantit[éeé] colis, col
    colis_pattern = r"(?i)\b(?:nombre\s+de\s+colis|nbr\s+colis|nbre\s+colis|nb\s+colis|n°\s*colis|qt[eé]?\s*colis|quantit[eé]?\s*colis|colis|col)\b\s*[:\-]?\s*(\d+)"
    # Pièces : nombre de pièces, nbr pièces, nb pièces, pcs, pce, qté pièces, qt[eé] pièces, unts, u
    pcs_pattern = r"(?i)\b(?:nombre\s+de\s+pi[eè]ces|nbr\s+pi[eè]ces|nb\s+pi[eè]ces|pcs|pce|qt[eé]?\s*pi[eè]ces|units?|u)\b\s*[:\-]?\s*(\d+)"
    # On cherche toutes les occurrences
    refs  = re.findall(ref_pattern, raw)
    colis = re.findall(colis_pattern, raw)
    pcs   = re.findall(pcs_pattern, raw)
    # On aligne sur la longueur min
    n = min(len(refs), len(colis), len(pcs))
    rows = []
    for i in range(n):
        try:
            c = int(colis[i])
            p = int(pcs[i])
        except:
            continue
        rows.append({
            "Référence": refs[i],
            "Nb de colis": c,
            "pcs par colis": p,
            "total": c * p,
            "Vérification": ""
        })
    return pd.DataFrame(rows)

# --- Parsing fallback 1 : 3 nombres sur la même ligne ---
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

# --- Parsing fallback 2 : séquentiel (3 lignes consécutives) ---
def parse_sequential(raw: str) -> pd.DataFrame:
    # Expression pour filtrer toutes lignes d'en-tête
    hdr = re.compile(r"(?i)^(date\b|nom du client\b|ref(erence)?\b|réf\b|nombre\s+de\s+colis\b|nbr\s+colis\b|nombre\s+de\s+pi[eè]ces\b)")
    lines = [l.strip() for l in raw.splitlines() if l.strip() and not hdr.match(l.strip())]
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

# --- Fallback orchestration ---
def parse_with_fallback(raw: str) -> pd.DataFrame:
    df = parse_keywords(raw)
    if not df.empty:
        return df
    st.warning("⚠️ Aucun mot-clé détecté → parsing générique…")
    df = parse_generic(raw)
    if not df.empty:
        return df
    st.warning("⚠️ Parsing générique vide → parsing séquentiel…")
    df = parse_sequential(raw)
    if df.empty:
        st.warning("⚠️ Aucune donnée détectée même en séquentiel.")
    return df

# --- Lecture d'un Excel structuré ---
def read_excel_bytes(x: bytes) -> pd.DataFrame:
    try:
        df = pd.read_excel(io.BytesIO(x))
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

# --- 1️⃣ Import ---
with st.container():
    st.markdown('<div class="card"><div class="section-title">1️⃣ Import du document</div>', unsafe_allow_html=True)
    uploaded = st.file_uploader("PDF / Image / Excel (.xlsx)", type=["pdf","jpg","jpeg","png","xlsx"])
    st.markdown('</div>', unsafe_allow_html=True)

if uploaded:
    data = uploaded.read()
    ext = uploaded.name.lower().rsplit(".",1)[-1]
    st.markdown(f"**Fichier** : `{uploaded.name}` — `{len(data)}` bytes")

    # --- 2️⃣ Extraction / OCR ---
    with st.container():
        st.markdown('<div class="card"><div class="section-title">2️⃣ Extraction du texte</div>', unsafe_allow_html=True)
        if ext == "xlsx":
            raw = None
        else:
            raw = extract_pdf_text(data) if ext=="pdf" else ""
            if not raw.strip():
                raw = google_ocr_pdf(data) if ext=="pdf" else google_ocr_image(data)
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
