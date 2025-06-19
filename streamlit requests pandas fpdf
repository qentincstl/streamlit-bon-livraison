import streamlit as st
import requests
import pandas as pd
from fpdf import FPDF
from io import BytesIO
import re

st.set_page_config(page_title="Bon de Livraison OCR", layout="centered")
st.title("📄 Extraction de bons de livraison manuscrits (OCR cloud)")

OCR_API_KEY = st.secrets["OCR_SPACE_API_KEY"]

def ocr_space_file(file, api_key):
    payload = {
        'isOverlayRequired': False,
        'apikey': api_key,
        'language': 'fre',
    }
    files = {'file': file}
    r = requests.post('https://api.ocr.space/parse/image',
                      files=files,
                      data=payload)
    return r.json()

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

uploaded_file = st.file_uploader("Déposez un PDF scanné (bon manuscrit)", type=["pdf"])

if uploaded_file:
    with st.spinner("🔍 Lecture OCR en cours..."):
        result = ocr_space_file(uploaded_file, OCR_API_KEY)
        try:
            text = result['ParsedResults'][0]['ParsedText']
            df = extract_data(text)
            st.success("✅ Extraction terminée !")
            st.dataframe(df)

            pdf_bytes = dataframe_to_pdf(df)
            st.download_button("📥 Télécharger les résultats en PDF", data=pdf_bytes, file_name="bon_livraison_resultat.pdf", mime="application/pdf")
        except:
            st.error("❌ Une erreur est survenue lors de la lecture OCR.")
