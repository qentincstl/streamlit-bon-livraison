import streamlit as st

st.set_page_config(page_title="Accueil logistique", page_icon="🚚", layout="wide")

st.markdown("""
    <h1 style='text-align:center; font-size:3rem;'>Accueil plateforme logistique</h1>
    <div style='display: flex; justify-content: center; gap: 4rem; margin-top: 3rem;'>
        <a href="/bon_de_livraison" target="_blank" style="text-decoration: none;">
            <div style='background:#f9f9f9; border-radius:1rem; padding:2rem; width:300px;
                        text-align:center; box-shadow:0 4px 10px rgba(0,0,0,0.1); transition: transform 0.2s;'>
                📦<h3>Bon de livraison</h3>
                <p>Déposer un bon de livraison et extraire les produits reçus.</p>
            </div>
        </a>

        <a href="/quantites_recues" target="_blank" style="text-decoration: none;">
            <div style='background:#f9f9f9; border-radius:1rem; padding:2rem; width:300px;
                        text-align:center; box-shadow:0 4px 10px rgba(0,0,0,0.1); transition: transform 0.2s;'>
                ✅<h3>Quantités réellement reçues</h3>
                <p>Saisir manuellement les quantités réceptionnées.</p>
            </div>
        </a>
    </div>
""", unsafe_allow_html=True)
