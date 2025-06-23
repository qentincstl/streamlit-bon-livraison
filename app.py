import streamlit as st
import pandas as pd
import openai, io, json, base64, hashlib
import fitz               # PyMuPDF
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
st.markdown("<h1 class=\"section-title\">Fiche de réception (OCR via GPT-4o Vision)</h1>", unsafe_allow_html=True)

# --- OpenAI KEY ---
OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", "")
if not OPENAI_API_KEY:
    st.error("🛑 Ajoutez `OPENAI_API_KEY` dans les Secrets de Streamlit Cloud.")
    st.stop()
openai.api_key = OPENAI_API_KEY

# --- Fonctions utilitaires ---
@st.cache_data(show_spinner=False)
def pdf_to_image(pdf_bytes: bytes) -> Image.Image:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pix = doc[0].get_pixmap(dpi=300)
    return Image.open(io.BytesIO(pix.tobytes("png")))

@st.cache_data(show_spinner=False)
def call_gpt4o_with_image(_img: Image.Image):
    buf = io.BytesIO(); _img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()

    fn_schema = {
        "name": "parse_delivery_note",
        "description": "Retourne un JSON : liste d'objets {reference, nb_colis, pcs_par_colis}",
        "parameters": {
            "type": "object",
            "properties": {
                "lines": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "reference": {"type": "string"},
                            "nb_colis": {"type": "integer"},
                            "pcs_par_colis": {"type": "integer"}
                        },
                        "required": ["reference", "nb_colis", "pcs_par_colis"]
                    }
                }
            },
            "required": ["lines"]
        }
    }

    resp = openai.chat.completions.create(
        model="gpt-4o",
        temperature=0,
        messages=[
            {"role": "system", "content":
                "Tu es un OCR spécialisé pour extraire les tableaux de bons de livraison manuscrits ou imprimés. "
                "Rends uniquement le JSON du tableau avec les champs référence, nb_colis, pcs_par_colis."
            },
            {"role": "user", "content": "Lis ce document et retourne le JSON structuré."}
        ],
        functions=[fn_schema],
        function_call={"name": "parse_delivery_note", "arguments": json.dumps({"image_base64": b64})}
    )
    return resp

# --- INTERFACE ---
st.markdown('<div class="card"><div class="section-title">1. Import du document</div></div>', unsafe_allow_html=True)
uploaded = st.file_uploader("Importez votre PDF ou photo de bon de livraison", key="file_uploader")

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
    data = json.loads(raw_json)['lines']
    df = pd.DataFrame(data).rename(columns={
        'reference': 'Référence',
        'nb_colis': 'Nb de colis',
        'pcs_par_colis': 'pcs par colis'
    })
    df['total'] = df['Nb de colis'] * df['pcs par colis']
    df['Vérification'] = ''
except Exception as e:
    st.error(f"Erreur lors du parsing JSON : {e}")
    st.stop()

st.markdown('<div class="card"><div class="section-title">4. Résultats</div>', unsafe_allow_html=True)
st.dataframe(df, use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="card"><div class="section-title">5. Export Excel</div>', unsafe_allow_html=True)
out = io.BytesIO()
with pd.ExcelWriter(out, engine="openpyxl") as writer:
    df.to_excel(writer, index=False, sheet_name="FICHE_DE_RECEPTION")
out.seek(0)
st.download_button("Télécharger la fiche de réception", data=out,
                   file_name="fiche_de_reception.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                   use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)

