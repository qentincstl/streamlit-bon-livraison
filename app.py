import streamlit as st
import pandas as pd
import openai, io, json, base64, time
import fitz               # PyMuPDF
from PIL import Image

# --- 0️⃣ Configuration page & style épuré ---
st.set_page_config(
    page_title="Fiche de réception",
    layout="wide",
)

st.markdown("""
<style>
  /* Fond et texte */
  .streamlit-container {
    background-color: #f8f9fa;
    color: #343a40;
  }
  /* Header */
  .header {
    font-size: 2.25rem;
    font-weight: 600;
    color: #005b96;
    margin-bottom: 1.5rem;
  }
  /* Cartes */
  .card {
    background: #ffffff;
    border: 1px solid #dee2e6;
    border-radius: 0.5rem;
    padding: 1.5rem;
    margin-bottom: 1.5rem;
  }
  /* Titres de section */
  .section-title {
    font-size: 1.5rem;
    font-weight: 500;
    color: #005b96;
    margin-bottom: 1rem;
  }
  /* Bouton de téléchargement */
  .stDownloadButton>button {
    background-color: #005b96;
    color: white;
    border: none;
    border-radius: 0.375rem;
    padding: 0.5rem 1rem;
  }
  .stDownloadButton>button:hover {
    background-color: #004170;
  }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="header">Fiche de réception</div>', unsafe_allow_html=True)

# --- 1️⃣ Init OpenAI (inchangé) ---
OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", "")
if not OPENAI_API_KEY:
    st.error("Veuillez définir votre clé OPENAI_API_KEY dans les Secrets.")
    st.stop()
openai.api_key = OPENAI_API_KEY

# --- 2️⃣ Helpers (PDF→Image & OCR) inchangés ---
def pdf_to_image(pdf_bytes: bytes) -> Image.Image:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pix = doc[0].get_pixmap(dpi=300)
    return Image.open(io.BytesIO(pix.tobytes("png")))

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
            args = resp.choices[0].message.function_call.arguments
            data = json.loads(args)
            df = pd.DataFrame(data["lines"])
            df = df.rename(columns={
                "reference":"Référence",
                "nb_colis":"Nb de colis",
                "pcs_par_colis":"pcs par colis"
            })
            df["total"] = df["Nb de colis"] * df["pcs par colis"]
            df["Vérification"] = ""
            return df
        except Exception as e:
            if attempt == 2:
                st.error(f"OCR échoué : {e}")
                return pd.DataFrame(columns=["Référence","Nb de colis","pcs par colis","total","Vérification"])
            time.sleep(2 ** attempt)

# --- 3️⃣ Interface utilisateur ---
st.markdown('<div class="card"><div class="section-title">1. Import du document</div>', unsafe_allow_html=True)
uploaded = st.file_uploader("", type=["pdf","jpg","jpeg","png"])
st.markdown('</div>', unsafe_allow_html=True)

if uploaded:
    raw = uploaded.read()
    ext = uploaded.name.lower().rsplit(".",1)[-1]

    # Conversion en image
    if ext == "pdf":
        img = pdf_to_image(raw)
    else:
        img = Image.open(io.BytesIO(raw))

    # Aperçu
    st.markdown('<div class="card"><div class="section-title">2. Aperçu</div>', unsafe_allow_html=True)
    st.image(img, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Extraction
    st.markdown('<div class="card"><div class="section-title">3. Extraction</div>', unsafe_allow_html=True)
    buf = io.BytesIO(); img.save(buf, format="PNG")
    df = extract_table_via_gpt(buf.getvalue())
    st.markdown('</div>', unsafe_allow_html=True)

    # Résultats
    st.markdown('<div class="card"><div class="section-title">4. Résultats</div>', unsafe_allow_html=True)
    st.dataframe(df, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Export
    st.markdown('<div class="card"><div class="section-title">5. Export Excel</div>', unsafe_allow_html=True)
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="FICHE_DE_RECEPTION")
    out.seek(0)
    st.download_button(
        label="Télécharger la fiche",
        data=out,
        file_name="fiche_de_reception.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    st.markdown('</div>', unsafe_allow_html=True)
