import streamlit as st

st.set_page_config(page_title="Accueil logistique", layout="wide")

if "page" not in st.session_state:
    st.session_state.page = "home"

def go(page):
    st.session_state.page = page

# -- CSS STYLE --
st.markdown("""
<style>
    body { background: #f7fafd; }
    .container-choice {
        display: flex; gap: 3.5rem; justify-content: center; align-items:center; margin-top:4.5rem;
    }
    .bigcard {
        width: 350px; min-height: 260px; background: #fff; border-radius: 1.2rem;
        box-shadow: 0 4px 18px #0002; padding:2.5rem 2rem;
        cursor:pointer; text-align:center; transition:.19s;
        border:2.5px solid #fff; position:relative;
        display:flex; flex-direction:column; align-items:center; justify-content:center;
    }
    .bigcard:hover {
        border:2.5px solid #3897f033;
        box-shadow: 0 7px 28px #257ee12b;
        transform: translateY(-7px) scale(1.04);
    }
    .bigicon { font-size:3.1rem; margin-bottom:1.6rem;}
    .title { font-size:1.45rem; font-weight:700; color:#133a5a;}
    .subtitle { font-size:1.07rem; color:#516080; margin-top:.75rem;}
</style>
""", unsafe_allow_html=True)

# --- PAGE LOGIC ---
if st.session_state.page == "home":
    st.markdown('<h1 style="text-align:center; color:#202944; margin-top:2rem; margin-bottom:2.4rem;">Accueil plateforme logistique</h1>', unsafe_allow_html=True)
    # Centered row with two clickable cards
    st.markdown('<div class="container-choice">', unsafe_allow_html=True)

    # Card 1
    st.markdown(f"""
        <div class="bigcard" onclick="window.parent.postMessage({{isStreamlitMessage:true,type:'streamlit:setComponentValue',key:'selected_page',value:'bl'}}, '*')">
            <div class="bigicon">📦</div>
            <div class="title">Bon de livraison</div>
            <div class="subtitle">Déposer un bon de livraison<br>et extraire les produits reçus.</div>
        </div>
    """, unsafe_allow_html=True)

    # Card 2
    st.markdown(f"""
        <div class="bigcard" onclick="window.parent.postMessage({{isStreamlitMessage:true,type:'streamlit:setComponentValue',key:'selected_page',value:'recues'}}, '*')">
            <div class="bigicon">✅</div>
            <div class="title">Quantités réellement reçues</div>
            <div class="subtitle">Saisir à la main les quantités<br>réellement réceptionnées.</div>
        </div>
    """, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

    # JS/CSS pour récupérer le clic sur card
    st.markdown("""
    <script>
        const cards = window.parent.document.querySelectorAll('.bigcard');
        if(cards.length === 2) {
            cards[0].onclick = () => window.location.search = '?page=bl';
            cards[1].onclick = () => window.location.search = '?page=recues';
        }
    </script>
    """, unsafe_allow_html=True)

    # Switch de page selon paramètre d'URL
    import urllib.parse
    params = st.query_params
    if params.get("page") == ["bl"]:
        go("bon_de_livraison")
    elif params.get("page") == ["recues"]:
        go("quantites_recues")

elif st.session_state.page == "bon_de_livraison":
    st.markdown('<h2>📦 Bon de livraison</h2>', unsafe_allow_html=True)
    if st.button("⬅️ Accueil", use_container_width=True):
        go("home")
    st.write("Ici ton module d'import + extraction automatique.")

elif st.session_state.page == "quantites_recues":
    st.markdown('<h2>✅ Quantités réellement reçues</h2>', unsafe_allow_html=True)
    if st.button("⬅️ Accueil", use_container_width=True):
        go("home")
    st.write("Ici ton module de saisie manuelle.")
