import streamlit as st

st.set_page_config(page_title="Gestion logistique", layout="wide")

# --- Définir l'état de la page ---
if "page" not in st.session_state:
    st.session_state.page = "home"

def go(page_name):
    st.session_state.page = page_name

# --- STYLE ---
st.markdown("""
    <style>
    .main {
        background: #f8fafc;
    }
    .bigcard {
        background: white;
        border-radius: 1.5rem;
        box-shadow: 0 4px 32px #0001;
        padding: 3rem 2.2rem;
        margin: 1.5rem 0;
        cursor: pointer;
        transition: transform 0.15s;
        text-align: center;
    }
    .bigcard:hover {
        transform: scale(1.025);
        box-shadow: 0 6px 32px #005aee22;
        border: 2px solid #4786ff22;
    }
    .bigicon {
        font-size: 3.5rem;
        margin-bottom: 1rem;
        color: #3483fa;
    }
    .title {
        font-size: 2rem;
        font-weight: 600;
        margin-bottom: 0.4rem;
        color: #005b96;
    }
    .subtitle {
        color: #888;
        font-size: 1.1rem;
    }
    </style>
""", unsafe_allow_html=True)

# --- PAGE ACCUEIL ---
if st.session_state.page == "home":
    st.markdown('<h1 style="text-align:center;color:#00274d;margin-top:1.2rem;margin-bottom:2.2rem;">Gestion logistique</h1>', unsafe_allow_html=True)
    col1, col2 = st.columns(2, gap="large")

    with col1:
        if st.button("", key="go_bl"):
            go("bon_de_livraison")
        st.markdown("""
        <div class="bigcard" onclick="window.parent.postMessage({type: 'streamlit:setComponentValue', value: 1}, '*'); document.querySelector('button[data-testid=stButton][key=go_bl]').click();">
            <div class="bigicon">📦</div>
            <div class="title">Bon de livraison</div>
            <div class="subtitle">Déposer un bon de livraison et extraire automatiquement les produits reçus.</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        if st.button("", key="go_real"):
            go("quantites_recues")
        st.markdown("""
        <div class="bigcard" onclick="window.parent.postMessage({type: 'streamlit:setComponentValue', value: 2}, '*'); document.querySelector('button[data-testid=stButton][key=go_real]').click();">
            <div class="bigicon">✅</div>
            <div class="title">Quantités réellement reçues</div>
            <div class="subtitle">Saisir à la main, ligne par ligne, les quantités réellement réceptionnées par l'usine.</div>
        </div>
        """, unsafe_allow_html=True)

# --- PAGE 1 : Bon de livraison (OCR & Extraction) ---
elif st.session_state.page == "bon_de_livraison":
    st.markdown('<h2 style="margin-top:1rem;">📦 Bon de livraison</h2>', unsafe_allow_html=True)
    st.button("⬅️ Retour à l'accueil", on_click=lambda: go("home"))
    st.write("**Importez ici votre bon de livraison (PDF ou image) pour extraction automatique.**")
    # 👉 Ici, colle tout ton code d’extraction OCR/GPT, le tableau, l’export, etc.

import pandas as pd
import openai
import io
import json
import base64
import hashlib
import fitz
from PIL import Image
import re

# Configuration de la page
st.set_page_config(
    page_title="Fiche de réception",
    layout="wide",
    page_icon="📋"
)

# CSS personnalisé
st.markdown("""
<style>
  .section-title { font-size:1.6rem; color:#005b96; margin-bottom:0.5rem; }
  .card { background:#fff; padding:1rem; border-radius:0.5rem;
          box-shadow:0 2px 4px rgba(0,0,0,0.07); margin-bottom:1.5rem; }
  .debug { font-size:0.9rem; color:#888; }
</style>
""", unsafe_allow_html=True)

st.markdown(
    '<h1 class="section-title">Fiche de réception (OCR multi-pages via GPT-4o Vision)</h1>',
    unsafe_allow_html=True
)

# Clé API OpenAI depuis les secrets Streamlit
OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", "")
if not OPENAI_API_KEY:
    st.error("🛑 Ajoutez `OPENAI_API_KEY` dans les Secrets de Streamlit Cloud.")
    st.stop()
openai.api_key = OPENAI_API_KEY

# --- Fonctions utilitaires ---

def extract_images_from_pdf(pdf_bytes: bytes):
    """Extrait chaque page du PDF en tant qu'image PIL."""
    images = []
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for page in doc:
        pix = page.get_pixmap(dpi=300)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        images.append(img)
    return images

def extract_json_with_gpt4o(img: Image.Image, prompt: str) -> str:
    """Envoie une image à GPT-4o avec le prompt et récupère la réponse brute."""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
            ]
        }],
        max_tokens=1500,
        temperature=0
    )
    return response.choices[0].message.content

def extract_json_block(s: str) -> str:
    """Isole le plus grand bloc JSON (entre {} ou []) dans une chaîne."""
    json_regex = re.compile(r'(\[.*?\]|\{.*?\})', re.DOTALL)
    matches = json_regex.findall(s)
    if not matches:
        raise ValueError("Aucun JSON trouvé dans la sortie du modèle.")
    return max(matches, key=len)

# Prompt pour GPT-4o
prompt = (
    "Tu es un assistant expert en logistique.\n"
    "Tu reçois un bon de livraison PDF, souvent sur plusieurs pages.\n"
    "Ta mission : extraire, consolider et restituer la liste des produits reçus sous forme de tableau Excel.\n"
    "\n"
    "Procédure à suivre :\n"
    "1. Lis chaque ligne du document et extrais les champs : Référence, Style, Marque, Produit, "
    "Nombre de colis, Nombre de pièces par colis, Total de pièces.\n"
    "2. Si un même article est présent sur plusieurs lignes, additionne les colis et quantités.\n"
    "3. Vérifie avec un récapitulatif global si disponible et signale les écarts dans 'Alerte'.\n"
    "4. Ignore les dimensions, poids, batch, etc.\n"
    "5. Formate la sortie en JSON array comme suit :\n"
    "[{\"Référence\": \"525017\", \"Style\": \"\", \"Marque\": \"\", "
    "\"Produit\": \"Muffins Chocolat\", \"Nombre de colis\": 12, "
    "\"Nombre de pièces\": 96, \"Total\": 816, \"Alerte\": \"\"}]\n"
    "Réponds uniquement par ce JSON, sans aucun texte supplémentaire."
)

# --- Interface utilisateur ---

# 1. Import du document
st.markdown(
    '<div class="card"><div class="section-title">1. Import du document</div></div>',
    unsafe_allow_html=True
)
uploaded = st.file_uploader(
    "Importez votre PDF (plusieurs pages) ou photo de bon de commande",
    key="file_uploader"
)
if not uploaded:
    st.stop()

file_bytes = uploaded.getvalue()
hash_md5 = hashlib.md5(file_bytes).hexdigest()
st.markdown(
    f'<div class="debug">Fichier : {uploaded.name} — Hash MD5 : {hash_md5}</div>',
    unsafe_allow_html=True
)

# Extraction des images
ext = uploaded.name.lower().rsplit('.', 1)[-1]
if ext == 'pdf':
    images = extract_images_from_pdf(file_bytes)
else:
    images = [Image.open(io.BytesIO(file_bytes))]

# 2. Aperçu du document
st.markdown(
    '<div class="card"><div class="section-title">2. Aperçu du document</div>',
    unsafe_allow_html=True
)
for i, img in enumerate(images):
    st.image(img, caption=f"Page {i+1}", use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)

# 3. Extraction JSON
all_lignes = []
st.markdown(
    '<div class="card"><div class="section-title">3. Extraction JSON</div>',
    unsafe_allow_html=True
)
for i, img in enumerate(images):
    st.markdown(f"##### Analyse page {i+1} …")
    success = False
    output, output_clean = None, None

    with st.spinner("Analyse en cours... (jusqu'à 6 essais automatiques)"):
        for attempt in range(1, 7):  # 6 tentatives
            try:
                output = extract_json_with_gpt4o(img, prompt)
                output_clean = extract_json_block(output)
                success = True
                break  # Succès, on sort
            except Exception:
                pass  # On retente

    st.code(output or "Aucune réponse retournée", language="json")

    if not success:
        st.error(f"Échec extraction JSON après 6 essais sur la page {i+1}. Texte brut retourné :\n{output}")
        continue

    try:
        lignes = json.loads(output_clean)
        all_lignes.extend(lignes)
    except Exception as e:
        st.error(f"Erreur parsing JSON page {i+1} : {e}")
st.markdown('</div>', unsafe_allow_html=True)

# 4. Affichage des résultats
df = pd.DataFrame(all_lignes)
st.markdown(
    '<div class="card"><div class="section-title">4. Résultats</div>',
    unsafe_allow_html=True
)
st.dataframe(df, use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)

# 5. Export Excel
st.markdown(
    '<div class="card"><div class="section-title">5. Export Excel</div>',
    unsafe_allow_html=True
)
out = io.BytesIO()
with pd.ExcelWriter(out, engine="openpyxl") as writer:
    df.to_excel(writer, index=False, sheet_name="BON_DE_LIVRAISON")
out.seek(0)
st.download_button(
    "Télécharger le fichier Excel",
    data=out,
    file_name="bon_de_livraison.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True
)
st.markdown('</div>', unsafe_allow_html=True)


# --- PAGE 2 : Quantités réellement reçues (Formulaire manuel) ---
elif st.session_state.page == "quantites_recues":
    st.markdown('<h2 style="margin-top:1rem;">✅ Quantités réellement reçues</h2>', unsafe_allow_html=True)
    st.button("⬅️ Retour à l'accueil", on_click=lambda: go("home"))
    st.write("**Saisissez les quantités reçues pour chaque produit.**")
    st.info("À personnaliser : tu peux mettre un tableau éditable, un formulaire, etc.")

    # Ex : Saisie dynamique (à étoffer selon besoin)
    n = st.number_input("Nombre de lignes à saisir :", 1, 50, 5)
    import pandas as pd
    import numpy as np
    df = pd.DataFrame(
        np.full((n, 5), ""),
        columns=["Référence", "Désignation", "Colis attendus", "Colis reçus", "Commentaire"]
    )
    edited = st.data_editor(df, key="saisie_recues", num_rows="dynamic")
    if st.button("Valider la saisie"):
        st.success("Données sauvegardées (exemple, à brancher à une base ou Excel)")import streamlit as st
