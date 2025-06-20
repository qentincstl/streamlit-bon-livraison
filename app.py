# app.py
import streamlit as st
import pandas as pd
import requests
import io
import re

st.set_page_config(page_title="Fiche de réception", layout="wide")
st.title("📥 Documents de réception → FICHE DE RECEPTION")

# OCR.space API (gratuit jusqu'à 25 000 car./j)
OCR_API_KEY = st.secrets.get("K82803521888957")

def ocr_space_file(file_bytes: bytes) -> str:
    api_key = st.secrets.get("OCR_SPACE_API_KEY", "")
    if not api_key:
        st.error("🛑 Clé OCR_SPACE_API_KEY introuvable dans secrets.toml")
        return ""
    payload = {
        "apikey": api_key,
        "language": "fre",
        "isOverlayRequired": False,
    }
    files = {"file": ("upload", file_bytes)}
    resp = requests.post("https://api.ocr.space/parse/image",
                         files=files, data=payload, timeout=60)
    # Ne pas lever automatiquement, mais inspecter
    if resp.status_code != 200:
        st.error(f"🛑 Erreur HTTP {resp.status_code} lors de l’appel OCR.space")
        st.text(resp.text)
        return ""
    result = resp.json()
    if result.get("IsErroredOnProcessing"):
        msg = result.get("ErrorMessage", ["Erreur inconnue"])[0]
        st.error(f"🛑 OCR.space a retourné une erreur: {msg}")
        return ""
    # Concatène tous les textes extraits
    return "\n".join(p["ParsedText"] for p in result.get("ParsedResults", []))

def parse_text_to_df(raw: str) -> pd.DataFrame:
    """
    Transforme le texte OCR en DataFrame avec colonnes :
    EAN, Désignation produits, Nb de colis, pcs par colis, total, Vérification
    """
    rows = []
    for line in raw.splitlines():
        line = line.strip()
        # on cherche : EAN (8–13 chiffres), texte désignation, nb_colis, pcs_colis
        m = re.match(r"^(\d{8,13})\s+(.+?)\s+(\d+)\s+(\d+)$", line)
        if m:
            ean, name, colis, pcs = m.groups()
            colis_i = int(colis)
            pcs_i = int(pcs)
            total = colis_i * pcs_i
            rows.append({
                "EAN": ean,
                "Désignation produits": name,
                "Nb de colis": colis_i,
                "pcs par colis": pcs_i,
                "total": total,
                "Vérification": ""
            })
    if not rows:
        st.warning("Aucune ligne valide détectée dans le texte OCR.")
    return pd.DataFrame(rows)

def read_excel_to_df(buf: io.BytesIO) -> pd.DataFrame:
    """Lit un Excel existant et le reformate/re-nomme ses colonnes si besoin."""
    df = pd.read_excel(buf)
    # on suppose qu'il contient déjà EAN, Désignation…, Nb de colis, pcs par colis
    df = df.rename(columns={
        df.columns[0]: "EAN",
        df.columns[1]: "Désignation produits",
        df.columns[2]: "Nb de colis",
        df.columns[3]: "pcs par colis"
    })
    df["total"] = df["Nb de colis"] * df["pcs par colis"]
    df["Vérification"] = ""
    return df[[
        "EAN", "Désignation produits",
        "Nb de colis", "pcs par colis",
        "total", "Vérification"
    ]]

uploaded = st.file_uploader(
    "📂 Déposez un PDF, image (JPG/PNG) ou un fichier Excel",
    type=["pdf", "jpg", "jpeg", "png", "xlsx"]
)

if uploaded:
    ext = uploaded.name.split(".")[-1].lower()
    if ext in ("xlsx",):
        # Lecture Excel
        df = read_excel_to_df(io.BytesIO(uploaded.read()))
    else:
        # OCR sur PDF ou image
        raw_text = ocr_space_file(uploaded)
        if raw_text:
            df = parse_text_to_df(raw_text)
        else:
            df = pd.DataFrame(columns=[
                "EAN", "Désignation produits",
                "Nb de colis", "pcs par colis",
                "total", "Vérification"
            ])
    st.success("✅ Données extraites")
    st.dataframe(df, use_container_width=True)

    # Préparation du fichier Excel à télécharger
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="FICHE DE RECEPTION")
    buffer.seek(0)
    st.download_button(
        label="📥 Télécharger la FICHE DE RECEPTION",
        data=buffer,
        file_name="fiche_de_reception.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
