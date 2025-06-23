import streamlit as st
import pandas as pd
import openai, io, json, base64, time, hashlib
import fitz               # PyMuPDF
from PIL import Image

# --- 0️⃣ Config page & style ---
st.set_page_config(page_title="Fiche de réception", layout="wide", page_icon="📋")
st.markdown("""
<style>
  .section-title { font-size:1.6rem; color:#005b96; margin-bottom:0.5rem; }
  .card { background:#fff; padding:1rem; border-radius:0.5rem;
          box-shadow:0 2px 4px rgba(0,0,0,0.1); margin-bottom:1.5rem; }
  .debug { font-size:0.9rem; color:#888; }
</style>
""", unsafe_allow_html=True)
st.markdown('<h1 class="section-title">Fiche de réception (OCR via OpenAI)</h1>', unsafe_allow_html=True)

# --- 1️⃣ Init OpenAI ---
OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY","")
if not OPENAI_API_KEY:
    st.error("🛑 Définit ta clé OPENAI_API_KEY dans les Secrets.")
    st.stop()
openai.api_key = OPENAI_API_KEY

# --- 2️⃣ Helpers PDF→Image + OCR-call ---
def pdf_to_image(pdf_bytes: bytes) -> Image.Image:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pix = doc[0].get_pixmap(dpi=300)
    return Image.open(io.BytesIO(pix.tobytes("png")))

def call_openai(b64: str):
    fn = {
      "name":"parse_delivery_note",
      "parameters":{
        "type":"object",
        "properties":{
          "lines":{
            "type":"array",
            "items":{
              "type":"object",
              "properties":{
                "reference":{"type":"string"},
                "nb_colis":{"type":"integer"},
                "pcs_par_colis":{"type":"integer"}
              },
              "required":["reference","nb_colis","pcs_par_colis"]
            }
          }
        },
        "required":["lines"]
      }
    }
    for i in range(3):
        try:
            resp = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role":"system","content":"Tu es un OCR/table-parser, strict JSON."},
                    {"role":"user","content":"Parse cette image et renvoie le JSON."}
                ],
                functions=[fn],
                function_call={"name":"parse_delivery_note",
                               "arguments":json.dumps({"image_base64":b64})}
            )
            return resp
        except Exception as e:
            if i==2:
                raise
            time.sleep(2**i)

# --- 3️⃣ UI de debug & upload ---
st.markdown('<div class="card"><div class="section-title">1. Import</div></div>', unsafe_allow_html=True)
uploaded = st.file_uploader("", type=["pdf","jpg","jpeg","png"])
if not uploaded:
    st.stop()

# Lire et calculer hash
file_bytes = uploaded.getvalue()
file_hash = hashlib.md5(file_bytes).hexdigest()
st.markdown(f'<div class="debug">🔍 Fichier: {uploaded.name} — Hash MD5: {file_hash}</div>',
            unsafe_allow_html=True)

# Convertir en PIL.Image
ext = uploaded.name.lower().rsplit(".",1)[-1]
img = pdf_to_image(file_bytes) if ext=="pdf" else Image.open(io.BytesIO(file_bytes))

# Aperçu
st.markdown('<div class="card"><div class="section-title">2. Aperçu</div>', unsafe_allow_html=True)
st.image(img, use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)

# Base64 & appel API
buf = io.BytesIO(); img.save(buf, format="PNG")
b64 = base64.b64encode(buf.getvalue()).decode()
resp = call_openai(b64)

# Afficher JSON brut pour debug
raw_args = resp.choices[0].message.function_call.arguments
st.markdown('<div class="card"><div class="section-title">3. JSON brut API</div>', unsafe_allow_html=True)
st.code(raw_args, language="json")
st.markdown('</div>', unsafe_allow_html=True)

# Parser en DataFrame
data = json.loads(raw_args)["lines"]
df = pd.DataFrame(data).rename(columns={
    "reference":"Référence",
    "nb_colis":"Nb de colis",
    "pcs_par_colis":"pcs par colis"
})
df["total"] = df["Nb de colis"] * df["pcs par colis"]
df["Vérification"] = ""

# Résultats
st.markdown('<div class="card"><div class="section-title">4. Résultats</div>', unsafe_allow_html=True)
st.dataframe(df, use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)

# Export
st.markdown('<div class="card"><div class="section-title">5. Export Excel</div>', unsafe_allow_html=True)
out = io.BytesIO()
with pd.ExcelWriter(out, engine="openpyxl") as w:
    df.to_excel(w, index=False, sheet_name="FICHE_DE_RECEPTION")
out.seek(0)
st.download_button("Télécharger la fiche", data=out,
                   file_name="fiche_de_reception.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                   use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)
