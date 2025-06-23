import streamlit as st
import pandas as pd
import openai, io, json, base64, time
import fitz  # PyMuPDF
from PIL import Image
import cv2
import numpy as np
import hashlib

# --- Configuration de la page & style ---
st.set_page_config(page_title="Fiche de réception", layout="wide", page_icon="📋")
st.markdown("""
<style>
  .section-title { font-size:1.6rem; color:#005b96; margin-bottom:0.5rem; }
  .card { background:#ffffff; padding:1rem; border-radius:0.5rem;
          box-shadow:0 2px 4px rgba(0,0,0,0.1); margin-bottom:1.5rem; }
  .debug { font-size:0.9rem; color:#666; margin-bottom:0.5rem; }
</style>
""", unsafe_allow_html=True)
st.markdown('<h1 class="section-title">Fiche de réception (OCR via GPT-4 Vision)</h1>', unsafe_allow_html=True)

# --- 1️⃣ Initialisation OpenAI ---
OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", "")
if not OPENAI_API_KEY:
    st.error("🛑 Veuillez définir OPENAI_API_KEY dans les Secrets.")
    st.stop()
openai.api_key = OPENAI_API_KEY

# --- 2️⃣ Fonctions utilitaires ---
def preprocess_image(img: Image.Image) -> Image.Image:
    # Binarisation Otsu pour augmenter le contraste du manuscrit
    gray = np.array(img.convert("L"))
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return Image.fromarray(thresh)


def pdf_to_image(pdf_bytes: bytes) -> Image.Image:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pix = doc[0].get_pixmap(dpi=300)
    return Image.open(io.BytesIO(pix.tobytes("png")))


def call_openai(b64: str) -> any:
    # Schéma de la fonction pour extraction structurée
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
    # Appel API avec retry et prompt strict
    for i in range(3):
        try:
            resp = openai.chat.completions.create(
                model="gpt-4o",
                temperature=0,
                messages=[
                    {"role": "system", "content": (
                        "Tu es un service OCR spécialisé pour bons de livraison manuscrits. "
                        "Extrait le tableau avec colonnes : Référence, Nombre de colis, pcs par colis. "
                        "Réponds uniquement par JSON conforme au schema." )},
                    {"role": "user", "content": "Analyse cette image et retourne le JSON."}
                ],
                functions=[fn_schema],
                function_call={"name": "parse_delivery_note", "arguments": json.dumps({"image_base64": b64})}
            )
            return resp
        except Exception as e:
            if i == 2:
                raise
            time.sleep(2 ** i)

# --- 3️⃣ Interface utilisateur & pipeline ---
st.markdown('<div class="card"><div class="section-title">1. Import du document</div></div>', unsafe_allow_html=True)
uploaded = st.file_uploader("")
if not uploaded:
    st.stop()

# Lecture et hash pour debug
file_bytes = uploaded.getvalue()
hash_md5 = hashlib.md5(file_bytes).hexdigest()
st.markdown(f'<div class="debug">Fichier: {uploaded.name} — Hash MD5: {hash_md5}</div>', unsafe_allow_html=True)

# Conversion en image
ext = uploaded.name.lower().rsplit('.', 1)[-1]
if ext == 'pdf':
    img = pdf_to_image(file_bytes)
else:
    img = Image.open(io.BytesIO(file_bytes))

# Pré-traitement pour manuscrit
img = preprocess_image(img)

# Aperçu
st.markdown('<div class="card"><div class="section-title">2. Aperçu</div>', unsafe_allow_html=True)
st.image(img, use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)

# Appel OpenAI
buf = io.BytesIO(); img.save(buf, format="PNG")
b64 = base64.b64encode(buf.getvalue()).decode()
resp = call_openai(b64)
raw_json = resp.choices[0].message.function_call.arguments

# Affichage JSON brut
st.markdown('<div class="card"><div class="section-title">3. JSON brut de l'API</div>', unsafe_allow_html=True)
st.code(raw_json, language="json")
st.markdown('</div>', unsafe_allow_html=True)

# Construction DataFrame
data = json.loads(raw_json)['lines']
df = pd.DataFrame(data).rename(columns={
    'reference': 'Référence',
    'nb_colis': 'Nb de colis',
    'pcs_par_colis': 'pcs par colis'
})
df['total'] = df['Nb de colis'] * df['pcs par colis']
df['Vérification'] = ''

# Résultats
st.markdown('<div class="card"><div class="section-title">4. Résultats</div>', unsafe_allow_html=True)
st.dataframe(df, use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)

# Export Excel
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
