import streamlit as st
import pandas as pd
import requests
import io
import re

st.set_page_config(page_title="Fiche de réception", layout="wide")
st.title("📥 Documents de réception → FICHE DE RECEPTION")

# -----------------------------------------------------------------------------
# 1) OCR.space avec détection de type MIME
# -----------------------------------------------------------------------------
def ocr_space_file(uploaded_file) -> str:
    api_key = st.secrets.get("OCR_SPACE_API_KEY", "")
    if not api_key:
        st.error("🛑 Clé OCR_SPACE_API_KEY introuvable dans les Secrets Streamlit")
        return ""
    # lecture et détection extension
    data = uploaded_file.read()
    ext = uploaded_file.name.lower().split(".")[-1]
    if ext == "pdf":
        mime = "application/pdf"
    elif ext in ("jpg", "jpeg"):
        mime = "image/jpeg"
    elif ext == "png":
        mime = "image/png"
    else:
        st.error(f"🛑 Format non supporté : .{ext}")
        return ""
    files = {"file": (uploaded_file.name, data, mime)}
    payload = {"apikey": api_key, "language": "fre", "isOverlayRequired": False}
    resp = requests.post(
        "https://api.ocr.space/parse/image",
        files=files,
        data=payload,
        timeout=60
    )
    if resp.status_code != 200:
        st.error(f"🛑 Erreur HTTP {resp.status_code} depuis OCR.space")
        st.text(resp.text)
        return ""
    result = resp.json()
    if result.get("IsErroredOnProcessing"):
        msg = result.get("ErrorMessage", ["Erreur inconnue"])[0]
        st.error(f"🛑 OCR.space a retourné une erreur : {msg}")
        return ""
    # Concatène tout le texte détecté
    return "\n".join(p["ParsedText"] for p in result.get("ParsedResults", []))


# -----------------------------------------------------------------------------
# 2) Parser le texte brut en DataFrame standardisée
# -----------------------------------------------------------------------------
def parse_text_to_df(raw: str) -> pd.DataFrame:
    rows = []
    for line in raw.splitlines():
        line = line.strip()
        # On s'attend à : EAN (8–13 chiffres) + libellé + nb_colis + pcs_colis
        m = re.match(r"^(\d{8,13})\s+(.+?)\s+(\d+)\s+(\d+)$", line)
        if m:
            ean, name, colis, pcs = m.groups()
            colis_i = int(colis)
            pcs_i = int(pcs)
            rows.append({
                "EAN": ean,
                "Désignation produits": name,
                "Nb de colis": colis_i,
                "pcs par colis": pcs_i,
                "total": colis_i * pcs_i,
                "Vérification": ""
            })
    if not rows:
        st.warning("⚠️ Aucune ligne valide détectée via OCR.")
    return pd.DataFrame(rows)


# -----------------------------------------------------------------------------
# 3) Lecture des Excel d'entrée
# -----------------------------------------------------------------------------
def read_excel_to_df(buffer: io.BytesIO) -> pd.DataFrame:
    df = pd.read_excel(buffer)
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


# -----------------------------------------------------------------------------
# 4) Upload et traitement
# -----------------------------------------------------------------------------
uploaded = st.file_uploader(
    "📂 Déposez un PDF, une image (JPG/PNG) ou un fichier Excel",
    type=["pdf", "jpg", "jpeg", "png", "xlsx"]
)

if uploaded:
    ext = uploaded.name.lower().split(".")[-1]
    if ext == "xlsx":
        df = read_excel_to_df(io.BytesIO(uploaded.read()))
    else:
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

    # Génère le fichier Excel de sortie
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="FICHE DE RECEPTION")
    output.seek(0)
    st.download_button(
        label="📥 Télécharger la FICHE DE RECEPTION",
        data=output,
        file_name="fiche_de_reception.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
