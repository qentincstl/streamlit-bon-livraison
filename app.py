import streamlit as st
import pandas as pd
import openai, io, re
import fitz                # PyMuPDF
from PIL import Image
import base64

# --- 0️⃣ Page config & style ---
st.set_page_config(page_title="Fiche de réception", layout="wide", page_icon="📋")
st.markdown("""
<style>
  .card { background:white; padding:1.5rem; border-radius:0.5rem;
          box-shadow:0 4px 6px rgba(0,0,0,0.1); margin-bottom:2rem;}
  .section-title { font-size:1.6rem; color:#4A90E2; margin-bottom:0.5rem;}
  .debug { background:#f0f0f0; padding:0.5rem; border-radius:0.25rem; font-family:monospace;}
</style>
""", unsafe_allow_html=True)
st.markdown(
  '<div class="section-title">📥 Documents de réception → FICHE DE RÉCEPTION</div>',
  unsafe_allow_html=True
)

# --- 1️⃣ Clé OpenAI & init ---
OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", "")
if not OPENAI_API_KEY:
    st.error("🛑 Définis `OPENAI_API_KEY` dans les Secrets.")
    st.stop()
openai.api_key = OPENAI_API_KEY

# --- 2️⃣ Test rapide de l’API OpenAI OCR (GPT-4V) ---
if st.button("🛠️ Tester OCR OpenAI"):
    # Génère une image avec le mot HELLO
    img = Image.new("RGB",(200,60),"white")
    from PIL import ImageDraw
    d = ImageDraw.Draw(img)
    d.text((10,10),"HELLO","black")
    buf = io.BytesIO(); img.save(buf,format="PNG")
    b = buf.getvalue()
    # Envoie à GPT-4 Vision via ChatCompletion
    resp = openai.ChatCompletion.create(
      model="gpt-4o-mini",       # ou "gpt-4-vision-preview"
      messages=[
        {"role":"system","content":"Tu es un OCR précis. Retourne juste le texte brut."},
        {"role":"user","content":"Extract text from this image."}
      ],
      functions=[{
        "name":"extract_text",
        "parameters":{"type":"object","properties":{"image_base64":{"type":"string"}},"required":["image_base64"]}
      }],
      function_call={"name":"extract_text","arguments":f'{{"image_base64":"{base64.b64encode(b).decode()}"}}'}
    )
    txt = resp["choices"][0]["message"]["content"]
    st.write("🔍 Texte détecté :", repr(txt))
    st.stop()

# --- 3️⃣ Fonctions utilitaires OCR & parsing ---

def ocr_openai_image(img_bytes: bytes) -> str:
    """
    Envoie l’image (base64) à GPT-4 Vision, récupération du texte brut.
    """
    b64 = base64.b64encode(img_bytes).decode()
    res = openai.ChatCompletion.create(
      model="gpt-4o-mini",       # remplacer par "gpt-4-vision-preview" si dispo
      messages=[
        {"role":"system","content":"Tu es un OCR précis. Retourne juste le texte brut, ligne par ligne."},
        {"role":"user","content":"Extract text from the provided image."}
      ],
      functions=[{
        "name":"extract_text",
        "parameters":{"type":"object","properties":{"image_base64":{"type":"string"}},"required":["image_base64"]}
      }],
      function_call={"name":"extract_text","arguments":f'{{"image_base64":"{b64}"}}'}
    )
    return res["choices"][0]["message"]["content"]

def pdf_to_image(pdf_bytes: bytes) -> Image.Image:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pix = doc[0].get_pixmap(dpi=300)
    return Image.open(io.BytesIO(pix.tobytes("png")))

def read_excel(buf: bytes) -> pd.DataFrame:
    df = pd.read_excel(io.BytesIO(buf))
    df = df.rename(columns={
      df.columns[0]:"Référence",
      df.columns[1]:"Nb de colis",
      df.columns[2]:"pcs par colis"
    })
    df["total"] = df["Nb de colis"]*df["pcs par colis"]
    df["Vérification"] = ""
    return df[["Référence","Nb de colis","pcs par colis","total","Vérification"]]

def parse_with_fallback(raw: str) -> pd.DataFrame:
    # Ton parsing robuste existant ici (parse_robust, parse_generic, parse_sequential)
    # …
    return df  # résultat du meilleur des 3 fallback

def ocr_by_columns_with_fallback(img: Image.Image) -> pd.DataFrame:
    w,h = img.size
    cuts = [0.3,0.6]
    boxes = [
      (0,0,int(w*cuts[0]),h),
      (int(w*cuts[0]),0,int(w*cuts[1]),h),
      (int(w*cuts[1]),0,w,h)
    ]
    zone_lines, counts = [], []
    for idx,(x1,y1,x2,y2) in enumerate(boxes,1):
        crop = img.crop((x1,y1,x2,y2))
        buf = io.BytesIO(); crop.save(buf,format="PNG")
        txt = ocr_openai_image(buf.getvalue())
        lines = [l.strip() for l in txt.splitlines() if l.strip()]
        zone_lines.append(lines)
        counts.append(len(lines))
        st.markdown(f"**Zone {idx} brut:**")
        st.markdown(f"<div class='debug'>{txt or '(vide)'}</div>",unsafe_allow_html=True)
    st.write(f"📊 Lignes détectées: Réf={counts[0]}, Colis={counts[1]}, Pièces={counts[2]}")
    n = min(*counts)
    if n>0:
      # Construire df comme avant…
      return df
    st.warning("⚠️ Aucune zone alignée ; fallback page entière…")
    full = ocr_openai_image(img_to_bytes(img))
    st.subheader("🔍 Texte complet OCR")
    st.text_area("", full or "(vide)", height=300)
    return parse_with_fallback(full)

# --- 4️⃣ Interface & workflow 4 conteneurs (Import → Extraction → Résultats → Export) ---
# À copier-coller tel quel depuis ta version précédente, 
# en remplaçant simplement les appels à Google Vision par ocr_openai_image / ocr_by_columns_with_fallback.
