def ocr_space_file(uploaded_file) -> str:
    st.info("🔍 [DEBUG] ocr_space_file() appelé")
    api_key = st.secrets.get("OCR_SPACE_API_KEY", "")
    st.write(f"[DEBUG] Clé présente: {bool(api_key)}")
    if not api_key:
        st.error("🛑 Clé OCR_SPACE_API_KEY manquante")
        return ""
    uploaded_file.seek(0)
    data = uploaded_file.read()
    ext = uploaded_file.name.lower().split(".")[-1]
    mime = {
        "pdf": "application/pdf",
        "jpg": "image/jpeg", "jpeg": "image/jpeg",
        "png": "image/png"
    }.get(ext)
    if not mime:
        st.error(f"🛑 Format non supporté : .{ext}")
        return ""

    resp = requests.post(
        "https://api.ocr.space/parse/image",
        files={"file": (uploaded_file.name, data, mime)},
        data={"apikey": api_key, "language": "fre", "isOverlayRequired": False},
        timeout=60
    )
    st.subheader("📋 JSON brut OCR.space")
    st.code(resp.text, language="json")  # scrollable

    if resp.status_code != 200:
        st.error(f"🛑 HTTP {resp.status_code} depuis OCR.space")
        return ""
    j = resp.json()
    if j.get("IsErroredOnProcessing"):
        st.error("🛑 OCR.space a retourné une erreur: " + str(j.get("ErrorMessage")))
        return ""
    texts = [p.get("ParsedText","") for p in j.get("ParsedResults",[])]
    full = "\n".join(texts)
    st.write(f"✏️ [DEBUG] OCR.text length = {len(full)}")
    return full
