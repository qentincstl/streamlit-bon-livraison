import streamlit as st
import pandas as pd
import openai, io, json, base64
import fitz
from PIL import Image

# --- 0️⃣ Config page & style ---
st.set_page_config(page_title="Fiche de réception", layout="wide", page_icon="📋")

# --- 1️⃣ Clé OpenAI ---
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
openai.api_key = OPENAI_API_KEY

# --- 2️⃣ PDF→Image ---
def pdf_to_image(pdf_bytes: bytes) -> Image.Image:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pix = doc[0].get_pixmap(dpi=300)
    return Image.open(io.BytesIO(pix.tobytes("png")))

# --- 3️⃣ Extraction table via GPT-4 Vision + Functions v2 ---
def extract_table_via_gpt(img_bytes: bytes) -> pd.DataFrame:
    b64 = base64.b64encode(img_bytes).decode()
    fn_schema = {
        "name": "parse_delivery_note",
        "description": "Retourne la liste des lignes {reference, nb_colis, pcs_par_colis}",
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

    resp = openai.chat.completions.create(
        model="gpt-4o-mini",  # ou "gpt-4-vision-preview"
        messages=[
            {"role":"system","content":"Tu es un OCR-table-parser, renvoie strictement du JSON."},
            {"role":"user","content":"Analyse cette image et retourne JSON."}
        ],
        functions=[fn_schema],
        function_call={"name":"parse_delivery_note","arguments": json.dumps({"image_base64": b64})}
    )
    func_args = resp.choices[0].message.function_call.arguments
    data = json.loads(func_args)
    df = pd.DataFrame(data["lines"])
    df = df.rename(columns={
        "reference":"Référence",
        "nb_colis":"Nb de colis",
        "pcs_par_colis":"pcs par colis"
    })
    df["total"] = df["Nb de colis"] * df["pcs par colis"]
    df["Vérification"] = ""
    return df

# --- 4️⃣ UI & workflow réduit pour l’exemple ---
st.title("📥 Fiche de réception (GPT-4 Vision)")

uploaded = st.file_uploader("PDF / Image", type=["pdf","jpg","jpeg","png"])
if uploaded:
    raw = uploaded.read()
    ext = uploaded.name.rsplit(".",1)[-1].lower()

    if ext == "pdf":
        img = pdf_to_image(raw)
    else:
        img = Image.open(io.BytesIO(raw))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    st.image(img, caption="🔍 Image traitée", use_column_width=True)

    df = extract_table_via_gpt(buf.getvalue())
    st.dataframe(df, use_container_width=True)

    bufxlsx = io.BytesIO()
    with pd.ExcelWriter(bufxlsx, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="FICHE_DE_RECEPTION")
    bufxlsx.seek(0)
    st.download_button(
        "📥 Télécharger Excel",
        data=bufxlsx,
        file_name="fiche_de_reception.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
