import streamlit as st
import pandas as pd
import openai, io, json
import fitz               # PyMuPDF
from PIL import Image

# --- 0️⃣ Config page & style ---
st.set_page_config(page_title="Fiche de réception", layout="wide", page_icon="📋")
st.markdown("""
<style>
  .card { background:white; padding:1.5rem; border-radius:0.5rem;
          box-shadow:0 4px 6px rgba(0,0,0,0.1); margin-bottom:2rem; }
  .section-title { font-size:1.6rem; color:#4A90E2; margin-bottom:0.5rem; }
</style>
""", unsafe_allow_html=True)
st.markdown('<div class="section-title">📥 Documents de réception → FICHE DE RÉCEPTION</div>', unsafe_allow_html=True)

# --- 1️⃣ Clé OpenAI ---
OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY","")
if not OPENAI_API_KEY:
    st.error("🛑 Ajoute ta clé OPENAI_API_KEY dans les Secrets.")
    st.stop()
openai.api_key = OPENAI_API_KEY

# --- 2️⃣ Helper PDF→Image ---
def pdf_to_image(pdf_bytes: bytes) -> Image.Image:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pix = doc[0].get_pixmap(dpi=300)
    return Image.open(io.BytesIO(pix.tobytes("png")))

# --- 3️⃣ Fonction d’appel OCR+parsing via GPT-4 Vision ---
def extract_table_via_gpt(img_bytes: bytes) -> pd.DataFrame:
    # on encode l'image en base64
    b64 = base64.b64encode(img_bytes).decode()
    # on définit une fonction fictive pour récupérer JSON structuré
    fn_schema = {
        "name": "parse_delivery_note",
        "description": "Retourne la liste des lignes avec référence, nb_colis et pcs_par_colis",
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

    resp = openai.ChatCompletion.create(
        model="gpt-4o-mini",               # ou "gpt-4-vision-preview"
        messages=[
            {"role":"system","content":"Tu es un OCR-table-parser, retourne seulement JSON."},
            {"role":"user","content":"Parse this delivery note into JSON."}
        ],
        functions=[fn_schema],
        function_call={"name":"parse_delivery_note","arguments": json.dumps({"image_base64": b64})},
    )
    args = resp.choices[0].message.function_call.arguments
    data = json.loads(args)
    # on construit le DataFrame
    df = pd.DataFrame(data["lines"])
    df = df.rename(columns={
        "reference":"Référence",
        "nb_colis":"Nb de colis",
        "pcs_par_colis":"pcs par colis"
    })
    df["total"] = df["Nb de colis"] * df["pcs par colis"]
    df["Vérification"] = ""
    return df

# --- 4️⃣ Interface utilisateur ---
with st.container():
    st.markdown('<div class="card"><div class="section-title">1️⃣ Import</div>', unsafe_allow_html=True)
    uploaded = st.file_uploader("PDF / Image / Excel (.xlsx)", type=["pdf","jpg","jpeg","png","xlsx"])
    st.markdown('</div>', unsafe_allow_html=True)

if uploaded:
    raw = uploaded.read()
    ext = uploaded.name.lower().split(".")[-1]

    # Excel structuré
    if ext == "xlsx":
        df = pd.read_excel(io.BytesIO(raw))
        df = df.rename(columns={
            df.columns[0]:"Référence",
            df.columns[1]:"Nb de colis",
            df.columns[2]:"pcs par colis"
        })
        df["total"] = df["Nb de colis"] * df["pcs par colis"]
        df["Vérification"] = ""

    # PDF ou Image → GPT-4 Vision
    else:
        img = pdf_to_image(raw) if ext=="pdf" else Image.open(io.BytesIO(raw))
        buf = io.BytesIO(); img.save(buf, format="PNG")
        df = extract_table_via_gpt(buf.getvalue())

    # Affichage & export
    with st.container():
        st.markdown('<div class="card"><div class="section-title">2️⃣ Résultats</div>', unsafe_allow_html=True)
        st.dataframe(df, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="card"><div class="section-title">3️⃣ Export Excel</div>', unsafe_allow_html=True)
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine="openpyxl") as w:
            df.to_excel(w, index=False, sheet_name="FICHE_DE_RECEPTION")
        out.seek(0)
        st.download_button("📥 Télécharger la fiche", data=out,
                           file_name="fiche_de_reception.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
