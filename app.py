import streamlit as st
import pandas as pd
import openai, io, json, base64, hashlib, re
import fitz             # PyMuPDF
from PIL import Image

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Fiche de réception", layout="wide", page_icon="📋")
st.markdown("""
<style>
  .section-title { font-size:1.6rem; color:#005b96; margin-bottom:0.5rem; }
  .card { background:#fff; padding:1rem; border-radius:0.5rem;
          box-shadow:0 2px 4px rgba(0,0,0,0.07); margin-bottom:1.5rem; }
  .debug { font-size:0.9rem; color:#888; }
</style>
""", unsafe_allow_html=True)
st.markdown("<h1 class=\"section-title\">Fiche de réception (OCR multi-pages via GPT-4o)</h1>", unsafe_allow_html=True)

# --- OPENAI KEY ---
OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", "")
if not OPENAI_API_KEY:
    st.error("🛑 Ajoutez `OPENAI_API_KEY` dans les Secrets.")
    st.stop()
openai.api_key = OPENAI_API_KEY

# --- UTILITAIRES ---
def extract_images_from_pdf(pdf_bytes: bytes):
    imgs = []
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for page in doc:
        pix = page.get_pixmap(dpi=300)
        imgs.append(Image.open(io.BytesIO(pix.tobytes("png"))))
    return imgs

def extract_json_block(s: str) -> str:
    m = re.findall(r'(\[.*?\]|\{.*?\})', s, flags=re.DOTALL)
    if not m:
        raise ValueError("Aucun JSON trouvé.")
    return max(m, key=len)

def call_gpt4o_with_image(img: Image.Image, prompt: str) -> str:
    # Convertit l'image en base64
    buf = io.BytesIO(); img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    # Crée un seul content texte avec prompt + image
    content = prompt + "\n\n[IMAGE_BASE64]\n" + b64
    res = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role":"system", "content": content}
        ],
        temperature=0,
        max_tokens=1500
    )
    return res.choices[0].message.content

# --- TON PROMPT MÉTIER ---
prompt = (
    "Tu es un assistant expert en logistique.\n"
    "Tu reçois un bon de livraison PDF (plusieurs pages).\n"
    "Ta mission : extraire et consolider la liste des produits reçus.\n"
    "Pour chaque produit, retourne un objet JSON avec ces champs :\n"
    "  - Référence (texte)\n"
    "  - EAN (texte)\n"
    "  - Style (texte)\n"
    "  - Marque (texte)\n"
    "  - Produit (texte)\n"
    "  - Nombre de colis (entier)\n"
    "  - Nombre de pièces (entier)\n"
    "  - Total (entier)\n"
    "  - Alerte (texte)\n"
    "1) Lis toutes les pages (image) et tous les tableaux.\n"
    "2) Si un même article apparaît plusieurs fois, fais la somme des colis et pièces.\n"
    "3) Ignore les dimensions, poids, batch, etc.\n"
    "4) Si le document contient un total global, utilise-le pour vérifier et note tout écart dans 'Alerte'.\n"
    "Réponds **SEULEMENT** par un **JSON array**.\n"
    "Exemple :\n"
    "[{\"Référence\":\"525017\",\"EAN\":\"3564700012591\","
    "\"Style\":\"\",\"Marque\":\"\",\"Produit\":\"Muffins Chocolat\","
    "\"Nombre de colis\":12,\"Nombre de pièces\":96,\"Total\":816,\"Alerte\":\"\"}]"
)

# --- UI STREAMLIT ---
st.markdown('<div class="card"><div class="section-title">1. Import du document</div></div>', unsafe_allow_html=True)
uploaded = st.file_uploader("Importez votre PDF multi-pages ou une image", type=["pdf","jpg","png"])
if not uploaded:
    st.stop()

file_bytes = uploaded.getvalue()
hash_md5 = hashlib.md5(file_bytes).hexdigest()
st.markdown(f'<div class="debug">Fichier : {uploaded.name} — Hash MD5 : {hash_md5}</div>', unsafe_allow_html=True)

# Extraction images
ext = uploaded.name.lower().rsplit(".",1)[-1]
images = extract_images_from_pdf(file_bytes) if ext=="pdf" else [Image.open(io.BytesIO(file_bytes))]

# Aperçu
st.markdown('<div class="card"><div class="section-title">2. Aperçu</div>', unsafe_allow_html=True)
for i,img in enumerate(images):
    st.image(img, caption=f"Page {i+1}", use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)

# Extraction & parsing
all_lines = []
st.markdown('<div class="card"><div class="section-title">3. Extraction JSON</div>', unsafe_allow_html=True)
for i,img in enumerate(images):
    st.markdown(f"##### Analyse page {i+1}")
    try:
        out = call_gpt4o_with_image(img, prompt)
        st.code(out, language="json")
        clean = extract_json_block(out)
        lines = json.loads(clean)
        all_lines.extend(lines)
    except Exception as e:
        st.error(f"Erreur page {i+1} : {e}")
st.markdown('</div>', unsafe_allow_html=True)

if not all_lines:
    st.error("Aucune donnée extraite.")
    st.stop()

# Résultats
df = pd.DataFrame(all_lines)
st.markdown('<div class="card"><div class="section-title">4. Résultats</div>', unsafe_allow_html=True)
st.dataframe(df, use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)

# Export Excel
st.markdown('<div class="card"><div class="section-title">5. Export Excel</div>', unsafe_allow_html=True)
buf = io.BytesIO()
with pd.ExcelWriter(buf, engine="openpyxl") as w:
    df.to_excel(w, index=False, sheet_name="BON_DE_LIVRAISON")
buf.seek(0)
st.download_button("Télécharger Excel", data=buf, file_name="bon_de_livraison.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                   use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)
