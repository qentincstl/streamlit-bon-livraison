# app.py
import streamlit as st
import requests, io, re
import fitz  # PyMuPDF
import pandas as pd

st.set_page_config(page_title="DEBUG 2", layout="wide")
st.write("✅ **App démarrée**")  # Vérif que le script est chargé

uploaded = st.file_uploader("📂 Déposez un PDF/PNG/JPG ou .xlsx", type=["pdf","jpg","jpeg","png","xlsx"])
st.write("📄 file_uploader retourné :", uploaded)

if uploaded is not None:
    st.write("✅ Fichier détecté :", uploaded.name)

    ext = uploaded.name.lower().split(".")[-1]
    st.write("🔍 Extension :", ext)

    # Test PDF textuel
    if ext == "pdf":
        try:
            st.write("📘 Tentative extract_pdf_text…")
            uploaded.seek(0)
            data = uploaded.read()
            doc = fitz.open(stream=data, filetype="pdf")
            txt = "\n".join(page.get_text() for page in doc)
            st.write(f"📘 Texte PDF brut ({len(txt)} chars):")
            st.text(txt[:500])
        except Exception as e:
            st.error("❌ extract_pdf_text erreur: " + str(e))

    # Test OCR.space brut
    st.write("📙 Tentative OCR.space…")
    api_key = st.secrets.get("OCR_SPACE_API_KEY", "")
    st.write("🔑 Clé OCR_SPACE_API_KEY chargée ?", bool(api_key))
    if api_key and ext in ("pdf","jpg","jpeg","png"):
        uploaded.seek(0)
        data = uploaded.read()
        mime = {
            "pdf": "application/pdf",
            "jpg":"image/jpeg","jpeg":"image/jpeg",
            "png":"image/png"
        }[ext]
        resp = requests.post(
            "https://api.ocr.space/parse/image",
            files={"file": (uploaded.name, data, mime)},
            data={"apikey": api_key, "language":"fre"},
            timeout=60
        )
        st.write("📋 OCR.space HTTP stat :", resp.status_code)
        st.subheader("📋 OCR.space raw JSON")
        st.code(resp.text, language="json")

    # On s'arrête là pour confirmer que l'UI et les appels fonctionnent
    st.stop()

st.write("ℹ️ Aucun fichier uploadé, fin de debug.")
