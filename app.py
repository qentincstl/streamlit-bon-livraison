import streamlit as st
import pandas as pd
import openai, io, json, base64, time
import fitz               # PyMuPDF
from PIL import Image

# --- Config page & style ---
st.set_page_config(page_title="Fiche de réception", layout="wide", page_icon="📋")
st.markdown("""
<style>
  .section-title { font-size:1.6rem; color:#005b96; margin-bottom:0.5rem; }
  .card { background:#fff; padding:1rem; border-radius:0.5rem;
          box-shadow:0 2px 4px rgba(0,0,0,0.1); margin-bottom:1.5rem; }
</style>
""", unsafe_allow_html=True)
st.markdown('<h1 class="section-title">Fiche de réception (OCR via OpenAI)</h1>', unsafe_allow_html=True)

# --- Init OpenAI ---
OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", "")
if not OPENAI_API_KEY:
    st.error("Ajoutez `OPENAI_API_KEY` dans les Secrets.")
    st.stop()
openai.api_key = OPENAI_API_KEY

# --- Helpers ---
def pdf_to_image(pdf_bytes: bytes) -> Image.Image:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pix = doc[0].get_pixmap(dpi=300)
    return Image.open(io.BytesIO(pix.tobytes("png")))

def extract_table(img: Image.Image) -> pd.DataFrame:
    # transforme l'image en bytes
    buf = io.BytesIO(); img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    # schéma de fonction
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
    # appel OpenAI
    for i in range(3):
        try:
            resp = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                  {"role":"system","content":"Tu es un OCR-table-parser, renvoie juste JSON."},
                  {"role":"user","content":"Parse cette image et retourne JSON structuré."}
                ],
                functions=[fn],
                function_call={"name":"parse_delivery_note","arguments":json.dumps({"image_base64":b64})}
            )
            args = resp.choices[0].message.function_call.arguments
            data = json.loads(args)["lines"]
            df = pd.DataFrame(data)
            df = df.rename(columns={
              "reference":"Référence",
              "nb_colis":"Nb de colis",
              "pcs_par_colis":"pcs par colis"
            })
            df["total"] = df["Nb de colis"]*df["pcs par colis"]
            df["Vérification"] = ""
            return df
        except Exception as e:
            if i==2:
                st.error(f"OCR échoué : {e}")
                return pd.DataFrame(columns=["Référence","Nb de colis","pcs par colis","total","Vérification"])
            time.sleep(2**i)

# --- UI ---
st.markdown('<div class="card"><div class="section-title">1. Import</div></div>', unsafe_allow_html=True)
uploaded = st.file_uploader("", type=["pdf","jpg","jpeg","png"])

if uploaded:
    raw = uploaded.read()
    ext = uploaded.name.lower().rsplit(".",1)[-1]

    # conversion
    if ext=="pdf":
        img = pdf_to_image(raw)
    else:
        img = Image.open(io.BytesIO(raw))

    # aperçu
    st.markdown('<div class="card"><div class="section-title">2. Aperçu</div>', unsafe_allow_html=True)
    st.image(img, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # extraction
    st.markdown('<div class="card"><div class="section-title">3. Extraction</div>', unsafe_allow_html=True)
    df = extract_table(img)
    st.markdown('</div>', unsafe_allow_html=True)

    # résultats
    st.markdown('<div class="card"><div class="section-title">4. Résultats</div>', unsafe_allow_html=True)
    st.dataframe(df, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # export
    st.markdown('<div class="card"><div class="section-title">5. Export Excel</div>', unsafe_allow_html=True)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="FICHE_DE_RECEPTION")
    buf.seek(0)
    st.download_button("Télécharger la fiche", data=buf,
                       file_name="fiche_de_reception.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)
