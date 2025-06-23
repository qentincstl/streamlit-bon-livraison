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

def call_gpt4o_with_image(img: Image.Image):
    buf = io.BytesIO(); img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()

    fn_schema = {
        "name": "extract_order_data",
        "description": "Retourne un JSON : liste d'objets {reference, style, marque, produit, nb_colis, nb_pieces, total}",
        "parameters": {
            "type": "object",
            "properties": {
                "lignes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "reference": {"type": "string"},
                            "style": {"type": "string"},
                            "marque": {"type": "string"},
                            "produit": {"type": "string"},
                            "nb_colis": {"type": "integer"},
                            "nb_pieces": {"type": "integer"},
                            "total": {"type": "number"}
                        },
                        "required": ["reference", "style", "marque", "produit", "nb_colis", "nb_pieces", "total"]
                    }
                }
            },
            "required": ["lignes"]
        }
    }

    resp = openai.chat.completions.create(
        model="gpt-4o",
        temperature=0,
        messages=[
            {
                "role": "system",
                "content":
"""Je vais uploader des bons de commande, et je souhaite que tu en extraies toutes les informations suivantes : la référence, le style, la marque, le produit, le nombre de colis, le nombre de pièces, le total. Ensuite, tu devras transformer ces données en un fichier Excel.

## Output Format
Le fichier Excel doit contenir une ligne par entrée extraite, avec les colonnes suivantes dans cet ordre :
- Référence (texte)
- Style (texte)
- Marque (texte)
- Produit (texte)
- Nombre de colis (nombre entier)
- Nombre de pièces (nombre entier)
- Total (nombre entier ou décimal)

Si une information est absente d’un bon de commande, laisse la cellule correspondante vide dans le fichier Excel."""
            },
            {
                "role": "user",
                "content": "Lis ce document et retourne le JSON structuré."
            }
        ],
        functions=[fn_schema],
        function_call={"name": "extract_order_data", "arguments": json.dumps({"image_base64": b64})}
    )
    return resp

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

st.markdown('<div class="card"><div class="section-title">3. Extraction & JSON brut</div>', unsafe_allow_html=True)
try:
    resp = call_gpt4o_with_image(img)
    raw_json = resp.choices[0].message.function_call.arguments
    st.code(raw_json, language="json")
except Exception as e:
    st.error(f"Erreur appel API : {e}")
    st.stop()
st.markdown('</div>', unsafe_allow_html=True)

try:
    lignes = json.loads(raw_json)['lignes']
    df = pd.DataFrame(lignes).rename(columns={
        'reference': 'Référence',
        'style': 'Style',
        'marque': 'Marque',
        'produit': 'Produit',
        'nb_colis': 'Nombre de colis',
        'nb_pieces': 'Nombre de pièces',
        'total': 'Total'
    })
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
