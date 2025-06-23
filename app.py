import streamlit as st
import pandas as pd
import openai, io, json, base64, time
import fitz               # PyMuPDF
from PIL import Image

# --- 0️⃣ Config page & CSS épuré ---
st.set_page_config(page_title="Fiche de réception", layout="wide")
st.markdown("""
<style>
  .section-title { font-size:1.6rem; color:#005b96; margin-bottom:0.5rem; }
  .card { background:#fff; padding:1rem; border-radius:0.5rem;
          box-shadow:0 2px 4px rgba(0,0,0,0.1); margin-bottom:1.5rem; }
</style>
""", unsafe_allow_html=True)
st.markdown('<h1 class="section-title">Fiche de réception (OCR via OpenAI)</h1>', unsafe_allow_html=True)

# --- 1️⃣ Init OpenAI ---
OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", "")
if not OPENAI_API_KEY:
    st.error("Ajoutez `OPENAI_API_KEY` dans les Secrets.")
    st.stop()
openai.api_key = OPENAI_API_KEY

# --- 2️⃣ Helpers ---
def pdf_to_image(pdf_bytes: bytes) -> Image.Image:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pix = doc[0].get_pixmap(dpi=300)
    return Image.open(io.BytesIO(pix.tobytes("png")))

def _call_openai(b64: str) -> list[dict]:
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
                  {"role":"system","content":"Tu es un OCR/table-parser, réponds strictement par JSON."},
                  {"role":"user","content":"Extract the table from this image and return JSON lines."}
                ],
                functions=[fn],
                function_call={"name":"parse_delivery_note",
                               "arguments": json.dumps({"image_base64":b64})}
            )
            return json.loads(r.choices[0].message.function_call.arguments)["lines"]
        except Exception:
            if i==2:
                raise
            time.sleep(2**i)

@st.cache_data(show_spinner=False)
def parse_delivery_note(file_bytes: bytes, ext: str) -> pd.DataFrame:
    # Convertit le fichier en PIL.Image
    if ext=="pdf":
        img = pdf_to_image(file_bytes)
    else:
        img = Image.open(io.BytesIO(file_bytes))
    # Encode en base64
    buf = io.BytesIO(); img.save(buf,format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    # Appel OpenAI
    lines = _call_openai(b64)
    # Construit le DataFrame
    df = pd.DataFrame(lines).rename(columns={
        "reference":"Référence",
        "nb_colis":"Nb de colis",
        "pcs_par_colis":"pcs par colis"
    })
    df["total"] = df["Nb de colis"] * df["pcs par colis"]
    df["Vérification"] = ""
    return df

# --- 3️⃣ UI & workflow ---
st.markdown('<div class="card"><div class="section-title">1. Import</div></div>', unsafe_allow_html=True)
uploaded = st.file_uploader("", type=["pdf","jpg","jpeg","png"])

if uploaded:
    raw = uploaded.read()
    ext = uploaded.name.lower().rsplit(".",1)[-1]

    # Preview
    st.markdown('<div class="card"><div class="section-title">2. Aperçu</div>', unsafe_allow_html=True)
    if ext=="pdf":
        st.image(pdf_to_image(raw), use_container_width=True)
    else:
        st.image(Image.open(io.BytesIO(raw)), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Parsing (cache invalidé si raw ou ext change)
    try:
        df = parse_delivery_note(raw, ext)
    except Exception as e:
        st.error(f"OCR échoué : {e}")
        df = pd.DataFrame(columns=["Référence","Nb de colis","pcs par colis","total","Vérification"])

    # Results
    st.markdown('<div class="card"><div class="section-title">3. Résultats</div>', unsafe_allow_html=True)
    st.dataframe(df, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Export
    st.markdown('<div class="card"><div class="section-title">4. Export Excel</div>', unsafe_allow_html=True)
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="FICHE_DE_RECEPTION")
    out.seek(0)
    st.download_button("Télécharger la fiche", data=out,
                       file_name="fiche_de_reception.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)
