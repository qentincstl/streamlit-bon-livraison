import streamlit as st
import pandas as pd
import openai, io, json, base64, time
import fitz               # PyMuPDF
from PIL import Image

# --- 0️⃣ Configuration de la page & style ---
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
OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", "")
if not OPENAI_API_KEY:
    st.error("🛑 Ajoutez `OPENAI_API_KEY` dans les Secrets de Streamlit Cloud.")
    st.stop()
openai.api_key = OPENAI_API_KEY

# --- 2️⃣ Helpers PDF→Image & OCR ---
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
                "reference": "Référence",
                "nb_colis": "Nb de colis",
                "pcs_par_colis": "pcs par colis"
            })
            df["total"] = df["Nb de colis"] * df["pcs par colis"]
            df["Vérification"] = ""
            return df
        except Exception as e:
            if attempt == 2:
                st.error(f"❌ OCR échoué : {e}")
                return pd.DataFrame(columns=["Référence","Nb de colis","pcs par colis","total","Vérification"])
            wait = 2 ** attempt
            st.warning(f"Erreur ({e.__class__.__name__}), nouvelle tentative dans {wait}s… ({attempt+1}/3)")
            time.sleep(wait)

# --- 3️⃣ Session state pour nettoyer à chaque nouvel upload ---
if "last_upload_id" not in st.session_state:
    st.session_state["last_upload_id"] = None
if "df" not in st.session_state:
    st.session_state["df"] = None

# --- 4️⃣ Uploader & traitement ---
st.markdown('<div class="card"><div class="section-title">1. Import du document</div>', unsafe_allow_html=True)
uploaded = st.file_uploader("", type=["pdf","jpg","jpeg","png"])
st.markdown('</div>', unsafe_allow_html=True)

if uploaded:
    # Identifiant unique du fichier (nom + taille)
    raw_bytes = uploaded.read()
    upload_id = f"{uploaded.name}_{len(raw_bytes)}"
    uploaded.seek(0)

    # Si nouveau fichier, réinitialiser le DataFrame
    if upload_id != st.session_state["last_upload_id"]:
        st.session_state["last_upload_id"] = upload_id
        st.session_state["df"] = None

    # Calculer le DataFrame seulement si n'existe pas encore pour ce fichier
    if st.session_state["df"] is None:
        ext = uploaded.name.lower().rsplit(".", 1)[-1]
        if ext == "pdf":
            img = pdf_to_image(raw_bytes)
        else:
            img = Image.open(io.BytesIO(raw_bytes))
        buf = io.BytesIO(); img.save(buf, format="PNG")
        st.session_state["df"] = extract_table_via_gpt(buf.getvalue())

    # Affichage et export du DataFrame en session
    df = st.session_state["df"]

    st.markdown('<div class="card"><div class="section-title">2. Résultats</div>', unsafe_allow_html=True)
    st.dataframe(df, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="card"><div class="section-title">3. Export Excel</div>', unsafe_allow_html=True)
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="FICHE_DE_RECEPTION")
    out.seek(0)
    st.download_button(
        label="Télécharger la fiche",
        data=out,
        file_name="fiche_de_reception.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )
    st.markdown('</div>', unsafe_allow_html=True)
