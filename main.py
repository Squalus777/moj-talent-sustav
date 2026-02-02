import streamlit as st
from modules.database import init_db, get_connection
from modules.auth import login_screen
from modules.views_mgr import render_manager_view
from modules.views_hr import render_hr_view
from modules.views_emp import render_employee_view # NOVI IMPORT

init_db()

if 'logged_in' not in st.session_state or not st.session_state['logged_in']:
    login_screen()
else:
    with st.sidebar:
        cid = st.session_state.get('company_id', 1)
        conn = get_connection()
        comp_name = conn.execute("SELECT name FROM companies WHERE id=?", (cid,)).fetchone()[0]
        
        st.title(f"🏢 {comp_name}")
        st.write(f"👤 **{st.session_state['username']}**")
        
        role = st.session_state.get('role', 'Employee')
        
        # Dinamičko prebacivanje uloga
        if role == 'Manager':
            mode = st.radio("Odaberi pogled:", ["👔 Moj Tim", "👤 Moji Podaci"])
            st.session_state['active_view'] = 'Manager' if "Tim" in mode else 'Employee'
        elif role == 'HR':
            st.session_state['active_view'] = 'HR'
        else:
            st.session_state['active_view'] = 'Employee'

        if st.button("Odjava"):
            st.session_state['logged_in'] = False
            st.rerun()

    # Routing
    view = st.session_state.get('active_view', 'Employee')
    if view == 'HR': render_hr_view()
    elif view == 'Manager': render_manager_view()
    else: render_employee_view()