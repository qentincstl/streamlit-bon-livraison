import streamlit as st

st.set_page_config(page_title="Plateforme logistique", layout="wide")

# --- STYLE ---
st.markdown("""
<style>
body {
    background-color: #F8FAFC;
}
.big-title {
    text-align: center;
    font-size: 2.6rem;
    color: #1a2233;
    font-weight: bold;
    margin-top: 2.5rem;
    margin-bottom: 2.5rem;
    letter-spacing: .01em;
}
.row {
    display: flex;
    justify-content: center;
    align-items: flex-start;
    gap: 3rem;
}
.card {
    background: #fff;
    border-radius: 1.2rem;
    box-shadow: 0 4px 16px 0 rgba(34,41,47,.09);
    padding: 2.5rem 2.5rem 2.3rem 2.5rem;
    min-width: 350px;
    max-width: 370px;
    min-height: 310px;
    text-align: center;
    cursor: pointer;
    border: 1.5px solid #ececec;
    transition: box-shadow 0.25s, border 0.2s;
}
.card:hover {
    border: 1.5px solid #447ddb;
    box-shadow: 0 8px 32px 0 rgba(68,125,219,0.15);
}
.card img {
    width: 70px;
    margin-bottom: 1.6rem;
}
.card-title {
    font-size: 1.5rem;
    color: #0c3b67;
    font-weight: 700;
    margin-bottom: 0.7rem;
}
.card-desc {
    font-size: 1.03rem;
    color: #435;
}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="big-title">Accueil plateforme logistique</div>', unsafe_allow_html=True)

# --- CARDS ---
col1, col2 = st.columns([1, 1], gap="large")

with col1:
    if st.button(
        label="Bon de livraison",
        key="btn_bon",
        help="Déposer un bon de livraison et extraire les produits reçus.",
        use_container_width=True
    ):
        st.switch_page("bon_de_livraison.py")
    st.markdown(
        """
        <div class="card">
            <img src="https://img.icons8.com/fluency/96/box.png"/>
            <div class="card-title">Bon de livraison</div>
            <div class="card-desc">Déposer un bon de livraison et extraire les produits reçus.</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with col2:
    if st.button(
        label="Quantités réellement reçues",
        key="btn_recu",
        help="Saisir à la main les quantités réellement réceptionnées.",
        use_container_width=True
    ):
        st.switch_page("reception_manuelle.py")
    st.markdown(
        """
        <div class="card">
            <img src="https://img.icons8.com/fluency/96/checked-checkbox.png"/>
            <div class="card-title">Quantités réellement reçues</div>
            <div class="card-desc">Saisir à la main les quantités réellement réceptionnées.</div>
        </div>
        """,
        unsafe_allow_html=True
    )
