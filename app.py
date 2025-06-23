import streamlit as st
import pandas as pd
import openai, io, json, base64, hashlib
import fitz
from PIL import Image

st.set_page_config(page_title="Fiche de réception", layout="wide", page_icon="📋")
st.markdown("""
<style>
  .section-title { font-size:1.6rem; color:#005b96; margin-bottom:0.5rem; }
  .card { background:#fff; padding:1rem; border-radius:0.5rem;
          box-shadow:0 2px 4px rgba(0,0,0,0.07); margin-bottom:1.5rem; }
  .debug { font-size:0.9rem; color:#888; }
</style>
""", unsafe_allow_html=True)
st.markdown("<h1 class=\"section-title\">Fiche de réception (OCR via GPT-4o Vision)</h1>", unsafe_allow_html=True)

OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", "")
if not OPENAI_API_KEY:
    st.error("🛑 Ajoutez `OPENAI_API_KEY` dans les Secrets de Streamlit Cloud.")
    st.stop()
openai.api_key = OPENAI_API_KEY

def pdf_to_image(pdf_bytes: bytes) -> Image.Image:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pix = doc[0].get_pixmap(dpi=300)
    return Image.open(io.BytesIO(pix.tobytes("png")))

def extract_json_with_gpt4o(img: Image.Image):
    buf = io.BytesIO(); img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()

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

# --- INTERFACE ---
st.markdown('<div class="card"><div class="section-title">1. Import du document</div></div>', unsafe_allow_html=True)
uploaded = st.file_uploader("Importez votre PDF ou photo de bon de commande", key="file_uploader")

if not uploaded:
    st.stop()

file_bytes = uploaded.getvalue()
hash_md5 = hashlib.md5(file_bytes).hexdigest()
st.markdown(f'<div class="debug">Fichier : {uploaded.name} — Hash MD5 : {hash_md5}</div>', unsafe_allow_html=True)

ext = uploaded.name.lower().rsplit('.', 1)[-1]
if ext == 'pdf':
    img = pdf_to_image(file_bytes)
else:
    img = Image.open(io.BytesIO(file_bytes))

st.markdown('<div class="card"><div class="section-title">2. Aperçu</div>', unsafe_allow_html=True)
st.image(img, use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="card"><div class="section-title">3. Extraction JSON</div>', unsafe_allow_html=True)
try:
    output = extract_json_with_gpt4o(img)
    st.code(output, language="json")
except Exception as e:
    st.error(f"Erreur appel API : {e}")
    st.stop()
st.markdown('</div>', unsafe_allow_html=True)

try:
    df = pd.DataFrame(json.loads(output))
except Exception as e:
    st.error(f"Erreur lors du parsing JSON : {e}")
    st.stop()

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
