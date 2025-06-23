import streamlit as st
import pandas as pd
import openai, io, json, base64, time
import fitz               # PyMuPDF
from PIL import Image

# --- 0️⃣ Config page & style ---
st.set_page_config(page_title="Fiche de réception", layout="wide", page_icon="📋")
st.markdown("""
<style>
  .section-title { font-size:1.6rem; color:#4A90E2; margin-bottom:0.5rem; }
  .card { background:white; padding:1rem; border-radius:0.5rem;
          box-shadow:0 2px 4px rgba(0,0,0,0.1); margin-bottom:1rem; }
</style>
""", unsafe_allow_html=True)
st.markdown('<h1 class="section-title">📥 Fiche de réception (OCR via OpenAI)</h1>', unsafe_allow_html=True)

# --- 1️⃣ Init OpenAI ---
OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", "")
if not OPENAI_API_KEY:
    st.error("🛑 Ajoute `OPENAI_API_KEY` dans les Secrets de Streamlit Cloud.")
    st.stop()
openai.api_key = OPENAI_API_KEY

# --- 2️⃣ Helper PDF→Image (1ʳᵉ page) ---
def pdf_to_image(pdf_bytes: bytes) -> Image.Image:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pix = doc[0].get_pixmap(dpi=300)
    return Image.open(io.BytesIO(pix.tobytes("png")))

# --- 3️⃣ OCR + parsing via GPT-3.5-turbo w/ retry backoff ---
def extract_table_via_gpt(img_bytes: bytes) -> pd.DataFrame:
    b64 = base64.b64encode(img_bytes).decode()
    fn_schema = {
        "name": "parse_delivery_note",
        "description": "Retourne JSON: liste de lignes {reference, nb_colis, pcs_par_colis}",
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
                        "required": ["reference","nb_colis","pcs_par_colis"]
                    }
                }
            },
            "required": ["lines"]
        }
    }

    for attempt in range(3):
        try:
            resp = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role":"system","content":"Tu es un OCR/table-parser, réponds strictement par JSON."},
                    {"role":"user","content":"Analyse cette image et retourne un JSON structuré de la table."}
                ],
                functions=[fn_schema],
                function_call={
                    "name":"parse_delivery_note",
                    "arguments": json.dumps({"image_base64": b64})
                }
            )
            # Lecture de la réponse
            args = resp.choices[0].message.function_call.arguments
            data = json.loads(args)
            df = pd.DataFrame(data["lines"])
            df = df.rename(columns={
                "reference": "Référence",
                "nb_colis": "Nb de colis",
                "pcs_par_colis": "pcs par colis"
            })
            df["total"] = df["Nb de colis"] * df["pcs par colis"]
            df["Vérification"] = ""
            return df

        except Exception as e:
            if attempt == 2:
                st.error(f"❌ OCR failed: {e}")
                return pd.DataFrame(
                    columns=["Référence","Nb de colis","pcs par colis","total","Vérification"]
                )
            wait = 2 ** attempt
            st.warning(f"Erreur ({e.__class__.__name__}), retry dans {wait}s… ({attempt+1}/3)")
            time.sleep(wait)

# --- 4️⃣ UI & workflow ---
uploaded = st.file_uploader("🗂️ Téléversez un PDF (1 page) ou une image", type=["pdf","jpg","jpeg","png"])
if uploaded:
    raw = uploaded.read()
    ext = uploaded.name.lower().rsplit(".", 1)[-1]

    # Convert / load image
    if ext == "pdf":
        img = pdf_to_image(raw)
    else:
        img = Image.open(io.BytesIO(raw))

    # Preview
    st.markdown('<div class="card"><div class="section-title">🔍 Aperçu</div>', unsafe_allow_html=True)
    st.image(img, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # OCR & parse
    buf = io.BytesIO(); img.save(buf, format="PNG")
    df = extract_table_via_gpt(buf.getvalue())

    # Show table
    st.markdown('<div class="card"><div class="section-title">📊 Résultats</div>', unsafe_allow_html=True)
    st.dataframe(df, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Export Excel
    st.mark
