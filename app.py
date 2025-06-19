import streamlit as st
import pytesseract
import fitz  # PyMuPDF
import pandas as pd
from PIL import Image
from fpdf import FPDF
from io import BytesIO
import re

st.set_page_config(page_title="📦 Bon de Livraison OCR", layout="centered")
st.title("📄 Extraction automatique des bons de livraison manuscrits")

uploaded_file = st.file_uploader("Déposez un bon de livraison manuscrit (PDF scanné) :", type=["pdf"])

def pdf_to_images(pdf_file):
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    images = []
    for page in doc:
        pix = page.get_pixmap(dpi=300)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        images.append(img)
    return images

def extract_text_from_images(images):
    text = ""
    for img in images:
        text += pytesseract.image_to_string(img, lang="fra") + "\n"
    return text

def extract_data(text):
    pattern = r"(?i)(\d+)\s*colis.*?(\d+)\s*pi[eè]ce.*?ref(?:[ée]rence)?\s*[:\-]?\s*(\S+)"
    matches = re.findall(pattern, text)
    data = []
    for match in matches:
        colis, pieces, ref = match
        commentaire = ""
        try:
            colis = int(colis)
            pieces = int(pieces)
        except:
            commentaire = "*Erreur corrigée"
        data.append({
            "Nombre de colis": colis,
            "Pièces par colis": pieces,
            "Référence": ref,
            "Commentaire": commentaire
        })
    if not data:
        data.append({
            "Nombre de colis": "",
            "Pièces par colis": "",
            "Référence": "",
            "Commentaire": "*Aucune donnée détectée"
        })
    return pd.DataFrame(data)

def dataframe_to_pdf(df):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    for i, row in df.iterrows():
        line = f"{row['Nombre de colis']} colis, {row['Pièces par colis']} pièces, Réf: {row['Référence']} {row['Commentaire']}"
        pdf.cell(200, 10, txt=line, ln=True)
    buffer = BytesIO()
    pdf.output(buffer)
    return buffer.getvalue()

if uploaded_file:
    with st.spinner("📄 Lecture et extraction en cours..."):
        images = pdf_to_images(uploaded_file)
        text = extract_text_from_images(images)
        df = extract_data(text)
        st.success("✅ Données extraites !")
        st.dataframe(df)

        pdf_bytes = dataframe_to_pdf(df)
        st.download_button("📥 Télécharger les résultats en PDF", data=pdf_bytes, file_name="bon_livraison_resultat.pdf", mime="application/pdf")
