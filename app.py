import streamlit as st
import pandas as pd
import openai, io, json, base64, time
import fitz                 # PyMuPDF
from PIL import Image

# --- 0️⃣ Configuration page & style ---
st.set_page_config(page_title="Fiche de réception", layout="wide", page_icon="📋")
st.markdown("""
<style>
  .section-title { font-size:1.6rem; color:#005b96; margin-bottom:0.5rem; }
  .card { background:#ffffff; padding:1rem; border-radius:0.5rem;
          box-shadow:0 2px 4px rgba(0,0,0,0.1); margin-bottom:1.5rem; }
</style>
""", unsafe_allow_html=True)
st.markdown('<h1 class="section-title">Fiche de réception (OCR via OpenAI)</h1>', unsafe_allow_html=True)

# --- 1️⃣ Init OpenAI ---
OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY","")
if not OPENAI_API_KEY:
    st.error("Ajoutez `OPENAI_API_KEY` dans les Secrets.")
    st.stop()
openai.api_key = OPENAI_API_KEY

# --- 2️⃣ Helpers PDF→Image & OCR-parser ---
def pdf_to_image(pdf_bytes: bytes) -> Image.Image:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pix = doc[0].get_pixmap(dpi=300)
    return Image.open(io.BytesIO(pix.tobytes("png")))

def extract_table(img: Image.Image) -> pd.DataFrame:
    buf = io.BytesIO(); img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
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
            r = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                  {"role":"system","content":"Tu es un OCR-table-parser, réponds juste du JSON."},
                  {"role":"user","content":"Extract the table from this image and return JSON."}
                ],
                functions=[fn],
                function_call={"name":"parse_delivery_note",
                               "arguments":json.dumps({"image_base64":b64})}
            )
            args = r.choices[0].message.function_call.arguments
            lines = json.loads(args)["lines"]
            df = pd.DataFrame(lines).rename(columns={
                "reference":"Référence",
                "nb_colis":"Nb de colis",
                "pcs_par_colis":"pcs par colis"
            })
            df["total"] = df["Nb de colis"] * df["pcs par colis"]
            df["Vérification"] = ""
            return df
        except Exception as e:
            if i==2:
                st.error(f"OCR échoué : {e}")
                return pd.DataFrame(columns=["Référence","Nb de colis","pcs par colis","total","Vérification"])
            time.sleep(2**i)

# --- 3️⃣ Callback & Session init ---
def _clear():
    # Lorsqu'on change de fichier, on relance tout à zéro
    st.session_state["df"] = None
    st.experimental_rerun()

if "df" not in st.session_state:
    st.session_state["df"] = None

# --- 4️⃣ Uploader avec on_change pour tout reset ---
st.markdown('<div class="card"><div class="section-title">1. Import</div></div>', unsafe_allow_html=True)
uploaded = st.file_uploader(
    label="",
    type=["pdf","jpg","jpeg","png"],
    key="uploader",
    on_change=_clear
)

# --- 5️⃣ Traitement sans conserver l’ancien résultat ---
if uploaded:
    raw = uploaded.read()
    ext = uploaded.name.lower().rsplit(".",1)[-1]

    # Conversion
    img = pdf_to_image(raw) if ext=="pdf" else Image.open(io.BytesIO(raw))

    # Aperçu
    st.markdown('<div class="card"><div class="section-title">2. Aperçu</div>', unsafe_allow_html=True)
    st.image(img, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Extraction (toujours recalculée après on_change)
    df = extract_table(img)

    # Résultats
    st.markdown('<div class="card"><div class="section-title">3. Résultats</div>', unsafe_allow_html=True)
    st.dataframe(df, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Export
    st.markdown('<div class="card"><div class="section-title">4. Export Excel</div>', unsafe_allow_html=True)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="FICHE_DE_RECEPTION")
    buf.seek(0)
    st.download_button("Télécharger la fiche", data=buf,
                       file_name="fiche_de_reception.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)
