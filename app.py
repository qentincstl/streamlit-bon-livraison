import streamlit as st
import pandas as pd
import requests
import io
import re
st.write("🔑 Clés chargées :", list(st.secrets.keys()))

st.set_page_config(page_title="Fiche de réception", layout="wide")
st.title("📥 Documents de réception → FICHE DE RECEPTION")

# -----------------------------------------------------------------------------
# Fonction OCR avec détection MIME pour OCR.space
# -----------------------------------------------------------------------------
def ocr_space_file(uploaded_file) -> str:
    """Appelle OCR.space en précisant le bon type MIME selon l'extension."""
    api_key = st.secrets.get("K82803521888957", "")
    if not api_key:
        st.error("🛑 Clé OCR_SPACE_API_KEY introuvable dans secrets.toml")
        return ""

    # Lecture des octets et détection de l'extension
    file_bytes = uploaded_file.read()
    ext = uploaded_file.name.split(".")[-1].lower()

    # Choix du MIME
    if ext == "pdf":
        mime = "application/pdf"
    elif ext in ("jpg", "jpeg"):
        mime = "image/jpeg"
    elif ext == "png":
        mime = "image/png"
    else:
        st.error(f"🛑 Type de fichier non supporté: .{ext}")
        return ""

    files = {"file": (uploaded_file.name, file_bytes, mime)}
    payload = {
        "apikey": api_key,
        "language": "fre",
        "isOverlayRequired": False
    }

    resp = requests.post(
        "https://api.ocr.space/parse/image",
        files=files,
        data=payload,
        timeout=60
    )
    if resp.status_code != 200:
        st.error(f"🛑 Erreur HTTP {resp.status_code} OCR.space")
        st.text(resp.text)
        return ""

    result = resp.json()
    if result.get("IsErroredOnProcessing"):
        msg = result.get("ErrorMessage", ["Erreur inconnue"])[0]
        st.error(f"🛑 OCR.space a retourné une erreur: {msg}")
        return ""

    # Concatène tous les blocs de texte extraits
    return "\n".join(p["ParsedText"] for p in result.get("ParsedResults", []))

# -----------------------------------------------------------------------------
# Parsing du texte OCR en DataFrame
# -----------------------------------------------------------------------------
def parse_text_to_df(raw: str) -> pd.DataFrame:
    """
    Transforme le texte OCR en DataFrame avec colonnes :
    EAN, Désignation produits, Nb de colis, pcs par colis, total, Vérification
    """
    rows = []
    for line in raw.splitlines():
        line = line.strip()
        # On cherche une ligne : EAN (8–13 chiffres), nom, nb_colis, pcs_colis
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
        st.warning("⚠️ Aucune ligne valide détectée dans le texte OCR.")
    return pd.DataFrame(rows)

# -----------------------------------------------------------------------------
# Lecture et conversion Excel d'entrée
# -----------------------------------------------------------------------------
def read_excel_to_df(buf: io.BytesIO) -> pd.DataFrame:
    """Lit un Excel existant et le reformate/re-nomme ses colonnes si besoin."""
    df = pd.read_excel(buf)
    # On suppose qu'il contient déjà les 4 colonnes dans l'ordre :
    # EAN, Désignation, Nb de colis, pcs par colis
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
# Upload et traitement
# -----------------------------------------------------------------------------
uploaded = st.file_uploader(
    "📂 Déposez un PDF, image (JPG/PNG) ou un fichier Excel",
    type=["pdf", "jpg", "jpeg", "png", "xlsx"]
)

if uploaded:
    ext = uploaded.name.split(".")[-1].lower()
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
