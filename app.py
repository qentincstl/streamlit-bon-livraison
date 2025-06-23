import streamlit as st
import pandas as pd
import openai, io, json, base64
import fitz
from PIL import Image

# … (la config et les fonctions extract_table_via_gpt / pdf_to_image restent inchangées) …

st.title("📥 Fiche de réception (GPT-4 Vision)")

uploaded = st.file_uploader("PDF / Image", type=["pdf","jpg","jpeg","png"])
if uploaded:
    raw = uploaded.read()
    ext = uploaded.name.rsplit(".",1)[-1].lower()

    # Convertit PDF>Image ou lit directement l’image
    if ext == "pdf":
        img = pdf_to_image(raw)
    else:
        img = Image.open(io.BytesIO(raw))

    # **Affiche l’image uploadée** avec la nouvelle option
    st.subheader("🔍 Aperçu de l’image uploadée")
    st.image(img, use_container_width=True)

    # OCR + parsing
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    df = extract_table_via_gpt(buf.getvalue())

    # Affiche le tableau
    st.subheader("📊 Résultats extraits")
    st.dataframe(df, use_container_width=True)

    # Export Excel
    buf_xlsx = io.BytesIO()
    with pd.ExcelWriter(buf_xlsx, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="FICHE_DE_RECEPTION")
    buf_xlsx.seek(0)
    st.download_button(
        "📥 Télécharger la fiche",
        data=buf_xlsx,
        file_name="fiche_de_reception.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )
