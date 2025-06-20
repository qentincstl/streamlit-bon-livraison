import streamlit as st
import pandas as pd
import requests, io, re
import fitz              # PyMuPDF
from PIL import Image

# --- Config de la page ---
st.set_page_config(
    page_title="Fiche de réception",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- CSS pour les cards et style épuré ---
st.markdown(
    """
    <style>
      .card {
        background-color: white;
        padding: 1.5rem;
        border-radius: 0.5rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin-bottom: 2rem;
      }
      .section-title {
        font-size: 1.6rem;
        margin-bottom: 0.5rem;
        color: #4A90E2;
      }
    </style>
    """,
    unsafe_allow_html=True
)

# --- Titre principal ---
st.markdown(
    '<div class="section-title">📥 Documents de réception → FICHE DE RÉCEPTION</div>',
    unsafe_allow_html=True
)

# --- Clé OCR.space (via Secrets UI) ---
OCR_KEY = st.secrets.get("OCR_SPACE_API_KEY", "")
if not OCR_KEY:
    st.error("🛑 Veuillez définir `OCR_SPACE_API_KEY` dans les Secrets de Streamlit Cloud.")
    st.stop()

# --- Extraction de texte si PDF « numérique » ---
def extract_pdf_text(pdf_bytes: bytes) -> str:
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        return "\n".join(page.get_text() for page in doc)
    except:
        return ""

# --- OCR d’une image via OCR.space ---
def ocr_image_bytes(img_bytes: bytes) -> str:
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

# --- OCR page par page pour un PDF scanné ---
def ocr_pdf_bytes(pdf_bytes: bytes) -> str:
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except:
        return ""
    full = ""
    for page in doc:
        pix = page.get_pixmap(dpi=300)
        png = pix.tobytes("png")
        full += ocr_image_bytes(png) + "\n"
    return full

# --- Parsing robuste des données ― références, colis, pièces ---
def parse_robust(raw: str) -> pd.DataFrame:
    """
    Reconnaît : 
      – toutes variantes de ref / référence 
      – nbr colis / nombre de colis / colis
      – pcs / pièces / nombre de pièces
    et aligne les triplets en tableau.
    """
    refs   = re.findall(r"(?i)(?:ref(?:[ée]rence)?|réf)\s*[:\-]?\s*(\S+)", raw)
    colis  = re.findall(r"(?i)(?:nombre\s*de\s*colis|nbr\s*colis|colis)\s*[:\-]?\s*(\d+)", raw)
    pieces = re.findall(
        r"(?i)(?:nombre\s*de\s*pi[eè]ces|pcs(?:\s*par\s*colis)?|pi[eè]ce?s?)\s*[:\-]?\s*(\d+)",
        raw
    )
    n = min(len(refs), len(colis), len(pieces))
    rows = []
    for i in range(n):
        c = int(colis[i])
        p = int(pieces[i])
        rows.append({
            "Référence": refs[i],
            "Nb de colis": c,
            "pcs par colis": p,
            "total": c * p,
            "Vérification": ""
        })
    if not rows:
        st.warning("⚠️ Aucune donnée détectée avec les mots-clés attendus.")
    return pd.DataFrame(rows)

# --- Lecture d’un Excel déjà structuré ---
def read_excel_bytes(xl_bytes: bytes) -> pd.DataFrame:
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
            "Référence","Nb de colis","pcs par colis","total","Vérification"
        ]]
    except Exception as e:
        st.error(f"❌ Erreur lecture Excel : {e}")
        return pd.DataFrame(columns=[
            "Référence","Nb de colis","pcs par colis","total","Vérification"
        ])

# --- 1️⃣ Import du document ---
with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">1️⃣ Import</div>', unsafe_allow_html=True)
    uploaded = st.file_uploader(
        "PDF (numérique ou manuscrit), image (JPG/PNG) ou Excel (.xlsx)",
        type=["pdf","jpg","jpeg","png","xlsx"]
    )
    st.markdown('</div>', unsafe_allow_html=True)

if uploaded:
    data = uploaded.read()
    ext = uploaded.name.lower().split(".")[-1]
    st.markdown(f"**Fichier** : `{uploaded.name}` — `{len(data)}` bytes")

    # --- 2️⃣ Extraction / OCR ---
    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">2️⃣ Extraction du texte</div>', unsafe_allow_html=True)

        # PDF numérique ?
        raw = extract_pdf_text(data) if ext == "pdf" else ""
        # sinon OCR (PDF scanné ou image)
        if not raw.strip():
            raw = ocr_pdf_bytes(data) if ext == "pdf" else ocr_image_bytes(data)

        # Affichage du texte brut
        st.subheader("📄 Texte brut extrait")
        st.text_area("", raw or "(vide)", height=200)

        # Conversion en DataFrame
        if ext == "xlsx":
            df = read_excel_bytes(data)
        else:
            df = parse_robust(raw or "")

        st.markdown('</div>', unsafe_allow_html=True)

    # --- 3️⃣ Résultats ---
    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">3️⃣ Résultats</div>', unsafe_allow_html=True)
        st.dataframe(df, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # --- 4️⃣ Export Excel ---
    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">4️⃣ Export Excel</div>', unsafe_allow_html=True)
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
