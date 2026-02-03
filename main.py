import streamlit as st
from modules.database import init_db, get_connection
from modules.auth import login_screen
from modules.views_mgr import render_manager_view
from modules.views_hr import render_hr_view
from modules.views_emp import render_employee_view

# 1. Inicijalizacija baze (kreiranje tablica goal_kpis, development_plans itd. ako ne postoje)
init_db()

# 2. Konfiguracija stranice - OBAVEZNO na vrhu za ispravan prikaz dashboarda i tablica
st.set_page_config(
    page_title="TommyTalent Management", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# 3. Provjera prijave
if 'logged_in' not in st.session_state or not st.session_state['logged_in']:
    login_screen()
else:
    # Dohvat uloge i osnovnih podataka iz sesije
    role = st.session_state.get('role', 'Employee')
    username = st.session_state.get('username')
    ime_prezime = st.session_state.get('ime_prezime', username)
    
    with st.sidebar:
        # Dinamički dohvat imena tvrtke iz baze
        try:
            cid = st.session_state.get('company_id', 1)
            conn = get_connection()
            comp_res = conn.execute("SELECT name FROM companies WHERE id=?", (cid,)).fetchone()
            comp_name = comp_res[0] if comp_res else "TommyTalent"
            conn.close()
        except:
            comp_name = "TommyTalent"
        
        st.title(f"🏢 {comp_name}")
        st.write(f"Korisnik: **{ime_prezime}**")
        st.write(f"Uloga: `{role}`")
        st.divider()
        
        # --- LOGIKA NAVIGACIJE (ROUTING) ---
        if role in ['HR', 'Admin']:
            # HR i Admin odmah idu na HR panel bez dodatnih pitanja
            st.session_state['active_view'] = 'HR'
        
        elif role == 'Manager':
            # Manager bira želi li vidjeti svoj tim ili svoje osobne procjene
            mode = st.radio("Navigacija:", ["👔 Moj Tim", "👤 Moji Podaci"])
            st.session_state['active_view'] = 'Manager' if "Tim" in mode else 'Employee'
        
        else:
            # Obični zaposlenici vide samo svoj profil
            st.session_state['active_view'] = 'Employee'

        st.spacer = st.container() # Estetski razmak
        
        if st.button("Odjava", use_container_width=True):
            st.session_state.clear() # Potpuno čišćenje sesije radi sigurnosti
            st.rerun()

    # --- RENDERIRANJE POGLEDA ---
    view = st.session_state.get('active_view', 'Employee')
    
    try:
        if view == 'HR': 
            render_hr_view() # Poziva restaurirani views_hr.py sa svim funkcijama
        elif view == 'Manager': 
            render_manager_view()
        else: 
            render_employee_view()
    except Exception as e:
        # Prikaz greške korisniku, ali i tehničkog detalja za lakši popravak
        st.error(f"Došlo je do pogreške pri učitavanju stranice.")
        st.warning(f"Detalj greške: {e}")
        if st.button("Pokušaj osvježiti stranicu"):
            st.rerun()