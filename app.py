import streamlit as st
import pandas as pd
import openai, io, json, base64, hashlib
import fitz
from PIL import Image
import re

st.set_page_config(page_title="Fiche de réception", layout="wide", page_icon="📋")
st.markdown("""
<style>
  .section-title { font-size:1.6rem; color:#005b96; margin-bottom:0.5rem; }
  .card { background:#fff; padding:1rem; border-radius:0.5rem;
          box-shadow:0 2px 4px rgba(0,0,0,0.07); margin-bottom:1.5rem; }
  .debug { font-size:0.9rem; color:#888; }
</style>
""", unsafe_allow_html=True)
st.markdown("<h1 class=\"section-title\">Fiche de réception (OCR multi-pages via GPT-4o Vision)</h1>", unsafe_allow_html=True)

OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", "")
if not OPENAI_API_KEY:
    st.error("🛑 Ajoutez `OPENAI_API_KEY` dans les Secrets de Streamlit Cloud.")
    st.stop()
openai.api_key = OPENAI_API_KEY

def extract_images_from_pdf(pdf_bytes: bytes):
    images = []
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for page in doc:
        pix = page.get_pixmap(dpi=300)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        images.append(img)
    return images

def extract_json_with_gpt4o(img: Image.Image, prompt: str):
    buf = io.BytesIO(); img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()

    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
                ]
            }
        ],
        max_tokens=1500,
        temperature=0
    )
    return response.choices[0].message.content

def extract_json_block(s):
    # Cherche le plus gros bloc entre crochets ou accolades
    json_regex = re.compile(r'(\[.*?\]|\{.*?\})', re.DOTALL)
    matches = json_regex.findall(s)
    if not matches:
        raise ValueError("Aucun JSON trouvé dans la sortie du modèle.")
    return max(matches, key=len)

prompt = (
    "Je vais uploader des bons de commande, et je souhaite que tu en extraies toutes les informations suivantes : "
    "la référence, le style, la marque, le produit, le nombre de colis, le nombre de pièces, le total. "
    "Ensuite, tu devras transformer ces données en un fichier Excel.\n\n"
    "Le fichier Excel doit contenir une ligne par entrée extraite, avec les colonnes suivantes dans cet ordre :\n"
    "- Référence (texte)\n- Style (texte)\n- Marque (texte)\n- Produit (texte)\n"
    "- Nombre de colis (nombre entier)\n- Nombre de pièces (nombre entier)\n- Total (nombre entier ou décimal)\n\n"
    "Si une information est absente d’un bon de commande, laisse la cellule correspondante vide dans le fichier Excel.\n"
    "Réponds uniquement avec le JSON correspondant à une liste d’objets dans cet ordre de colonnes, sans texte additionnel. "
    "Exemple :\n"
    "[{\"Référence\": \"12345\", \"Style\": \"A\", \"Marque\": \"Nike\", \"Produit\": \"Chaussure\", \"Nombre de colis\": 3, \"Nombre de pièces\": 5, \"Total\": 15}, ...]"
)

# --- INTERFACE ---
st.markdown('<div class="card"><div class="section-title">1. Import du document</div></div>', unsafe_allow_html=True)
uploaded = st.file_uploader("Importez votre PDF (plusieurs pages) ou photo de bon de commande", key="file_uploader")

if not uploaded:
    st.stop()

file_bytes = uploaded.getvalue()
hash_md5 = hashlib.md5(file_bytes).hexdigest()
st.markdown(f'<div class="debug">Fichier : {uploaded.name} — Hash MD5 : {hash_md5}</div>', unsafe_allow_html=True)

ext = uploaded.name.lower().rsplit('.', 1)[-1]
if ext == 'pdf':
    images = extract_images_from_pdf(file_bytes)
else:
    images = [Image.open(io.BytesIO(file_bytes))]

st.markdown('<div class="card"><div class="section-title">2. Aperçu du document</div>', unsafe_allow_html=True)
for i, img in enumerate(images):
    st.image(img, caption=f"Page {i+1}", use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)

# Extraction des données sur chaque page
all_lignes = []
st.markdown('<div class="card"><div class="section-title">3. Extraction JSON</div>', unsafe_allow_html=True)
for i, img in enumerate(images):
    st.markdown(f"##### Analyse page {i+1} ...")
    try:
        output = extract_json_with_gpt4o(img, prompt)
        st.code(output, language="json")
        output_clean = extract_json_block(output)
        lignes = json.loads(output_clean)
        all_lignes.extend(lignes)
    except Exception as e:
        st.error(f"Erreur extraction page {i+1} : {e}")
st.markdown('</div>', unsafe_allow_html=True)

if not all_lignes:
    st.error("Aucune donnée n'a été extraite du document.")
    st.stop()

df = pd.DataFrame(all_lignes)
st.markdown('<div class="card"><div class="section-title">4. Résultats</div>', unsafe_allow_html=True)
st.dataframe(df, use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="card"><div class="section-title">5. Export Excel</div>', unsafe_allow_html=True)
out = io.BytesIO()
with pd.ExcelWriter(out, engine="openpyxl") as writer:
    df.to_excel(writer, index=False, sheet_name="BON_DE_COMMANDE")
out.seek(0)
st.download_button("Télécharger le fichier Excel", data=out,
                   file_name="bon_de_commande.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                   use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)
