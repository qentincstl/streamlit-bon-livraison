import streamlit as st

st.set_page_config(page_title="Gestion logistique", layout="wide")

if "page" not in st.session_state:
    st.session_state.page = "home"

def go(page_name):
    st.session_state.page = page_name

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

elif st.session_state.page == "bon_de_livraison":
    st.markdown('<h2 style="margin-top:1rem;">📦 Bon de livraison</h2>', unsafe_allow_html=True)
    st.button("⬅️ Retour à l'accueil", on_click=lambda: go("home"))
    st.write("**Importez ici votre bon de livraison (PDF ou image) pour extraction automatique.**")
    # ICI : Colle ensuite tout ton code OCR d’extraction/tableau/export etc.

elif st.session_state.page == "quantites_recues":
    st.markdown('<h2 style="margin-top:1rem;">✅ Quantités réellement reçues</h2>', unsafe_allow_html=True)
    st.button("⬅️ Retour à l'accueil", on_click=lambda: go("home"))
    st.write("**Saisissez les quantités reçues pour chaque produit.**")
    st.info("À personnaliser : tu peux mettre un tableau éditable, un formulaire, etc.")

    import pandas as pd
    import numpy as np
    n = st.number_input("Nombre de lignes à saisir :", 1, 50, 5)
    df = pd.DataFrame(
        np.full((n, 5), ""),
        columns=["Référence", "Désignation", "Colis attendus", "Colis reçus", "Commentaire"]
    )
    edited = st.data_editor(df, key="saisie_recues", num_rows="dynamic")
    if st.button("Valider la saisie"):
        st.success("Données sauvegardées (exemple, à brancher à une base ou Excel)")
