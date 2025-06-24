import streamlit as st

st.set_page_config(page_title="Accueil logistique", layout="wide")

if "page" not in st.session_state:
    st.session_state.page = "home"

def go(page):
    st.session_state.page = page

st.markdown("""
    <style>
    body { background: #f7fafd; }
    .container-choice {display:flex; gap:3rem; justify-content:center; margin-top:2.5rem;}
    .bigcard {
        width: 350px; min-height: 230px; background: #fff; border-radius: 1.2rem;
        box-shadow: 0 4px 18px #0002; padding:2.5rem 1.8rem;
        cursor:pointer; text-align:center; transition:.17s;
        border:2.5px solid #fff;
        position:relative;
    }
    .bigcard:hover {
        border:2.5px solid #3a84ff33;
        box-shadow: 0 7px 28px #4683f62b;
        transform: translateY(-5px) scale(1.035);
    }
    .bigicon { font-size:2.8rem; color:#2568c3; margin-bottom:1.3rem;}
    .title { font-size:1.5rem; font-weight:600; color:#124079;}
    .subtitle { font-size:1rem; color:#6a7a90; margin-top:.5rem;}
    </style>
""", unsafe_allow_html=True)

if st.session_state.page == "home":
    st.markdown('<h1 style="text-align:center; color:#1a2947;">Accueil plateforme logistique</h1>', unsafe_allow_html=True)
    # fake columns for layout
    st.markdown('<div class="container-choice">', unsafe_allow_html=True)
    st.markdown(f"""
        <div class="bigcard" onclick="window.location.hash = 'bl'">
            <div class="bigicon">📦</div>
            <div class="title">Bon de livraison</div>
            <div class="subtitle">Déposer un bon de livraison et extraire les produits reçus.</div>
        </div>
        <div class="bigcard" onclick="window.location.hash = 'recues'">
            <div class="bigicon">✅</div>
            <div class="title">Quantités réellement reçues</div>
            <div class="subtitle">Saisir à la main les quantités réellement réceptionnées.</div>
        </div>
    """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Script to auto-refresh if hash changes (simulate navigation)
    st.markdown("""
    <script>
        window.addEventListener('hashchange', function() {
            window.parent.postMessage({isStreamlitMessage: true, type: 'streamlit:rerun'}, '*')
        });
    </script>
    """, unsafe_allow_html=True)

    # Redirige si hash présent
    js_hash = st.experimental_get_query_params()
    import streamlit as st
    import urllib.parse
    hashval = st.experimental_get_query_params()
    import streamlit as st
    import re
    hash_code = st.experimental_get_query_params()
    if st.query_params:
        import re
        if re.search(r"#bl", str(st.query_params)):
            go("bon_de_livraison")
        elif re.search(r"#recues", str(st.query_params)):
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
