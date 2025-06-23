import streamlit as st
import pandas as pd
import openai, io, json, base64, time
import fitz              # PyMuPDF
from PIL import Image

# --- Configuration de la page & style ---
st.set_page_config(page_title="Fiche de réception", layout="wide", page_icon="📋")
st.markdown("""
<style>
  .section-title { font-size:1.6rem; color:#4A90E2; margin-bottom:0.5rem; }
  .card { background:white; padding:1rem; border-radius:0.5rem;
          box-shadow:0 2px 4px rgba(0,0,0,0.1); margin-bottom:1rem; }
</style>
""", unsafe_allow_html=True)
st.markdown('<h1 class="section-title">📥 Fiche de réception (GPT-4 Vision)</h1>', unsafe_allow_html=True)

# --- 1️⃣ Init OpenAI ---
OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", "")
if not OPENAI_API_KEY:
    st.error("🛑 Définis `OPENAI_API_KEY` dans les Secrets.")
    st.stop()
openai.api_key = OPENAI_API_KEY

# --- 2️⃣ Helper : PDF → PIL.Image (1ʳᵉ page) ---
def pdf_to_image(pdf_bytes: bytes) -> Image.Image:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pix = doc[0].get_pixmap(dpi=300)
    return Image.open(io.BytesIO(pix.tobytes("png")))

# --- 3️⃣ OCR + parsing via GPT-4 Vision w/ retry simplifié ---
def extract_table_via_gpt(img_bytes: bytes) -> pd.DataFrame:
    b64 = base64.b64encode(img_bytes).decode()
    fn_schema = {
        "name": "parse_delivery_note",
        "description": "Retourne JSON : liste d'objets {reference, nb_colis, pcs_par_colis}",
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

    # Tentatives avec backoff
    for attempt in range(3):
        try:
            resp = openai.chat.completions.create(
                model="gpt-4o",   # ou "gpt-3.5-turbo" si le quota est trop serré
                messages=[
                    {"role":"system","content":"Tu es un OCR-table-parser, réponds uniquement par JSON."},
                    {"role":"user","content":"Parse cette image en JSON structuré."}
                ],
                functions=[fn_schema],
                function_call={
                    "name":"parse_delivery_note",
                    "arguments": json.dumps({"image_base64": b64})
                },
            )
            # Si on arrive ici, l'appel a fonctionné
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
            # Si c'est la dernière tentative, on alerte sinon on attend
            if attempt == 2:
                st.error(f"❌ Erreur OCR GPT-4 : {e}")
                return pd.DataFrame(columns=["Référence","Nb de colis","pcs par colis","total","Vérification"])
            wait = 2 ** attempt
            st.warning(f"Erreur ({e.__class__.__name__}), j’essaie à nouveau dans {wait}s…")
            time.sleep(wait)

# --- 4️⃣ Interface & workflow ---
uploaded = st.file_uploader("🗂️ Téléversez un PDF (1 page) ou une image", type=["pdf","jpg","jpeg","png"])
if uploaded:
    raw = uploaded.read()
    ext = uploaded.name.lower().rsplit(".",1)[-1]

    # 4.1 Convertir PDF ou charger image
    if ext == "pdf":
        img = pdf_to_image(raw)
    else:
        img = Image.open(io.BytesIO(raw))

    # 4.2 Affichage de l’image
    st.markdown('<div class="card"><div class="section-title">🔍 Aperçu de l’image</div>', unsafe_allow_html=True)
    st.image(img, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # 4.3 OCR + parsing
    buf = io.BytesIO(); img.save(buf, format="PNG")
    df = extract_table_via_gpt(buf.getvalue())

    # 4.4 Affichage du tableau
    st.markdown('<div class="card"><div class="section-title">📊 Résultats extraits</div>', unsafe_allow_html=True)
    st.dataframe(df, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # 4.5 Export Excel
    st.markdown('<div class="card"><div class="section-title">💾 Export Excel</div>', unsafe_allow_html=True)
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="FICHE_DE_RECEPTION")
    out.seek(0)
    st.download_button(
        "📥 Télécharger la fiche de réception",
        data=out,
        file_name="fiche_de_reception.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )
    st.markdown('</div>', unsafe_allow_html=True)
