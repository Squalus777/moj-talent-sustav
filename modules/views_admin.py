import streamlit as st
import pandas as pd
import sqlite3
from modules.database import get_connection, DB_FILE, log_action
from modules.utils import make_hashes

def render_admin_view():
    st.header("🛠️ Administracija Sustava")
    conn = get_connection()
    company_id = st.session_state.get('company_id', 1)

    st.subheader("🔑 Brzi reset lozinke")
    st.write("Koristi ovo samo ako zaposlenik zaboravi lozinku.")
    
    users_df = pd.read_sql_query("SELECT username, role FROM users WHERE company_id=?", conn, params=(company_id,))
    
    col1, col2 = st.columns(2)
    user_to_reset = col1.selectbox("Odaberi korisnika:", users_df['username'].tolist())
    new_pass = col2.text_input("Nova lozinka", type="password")
    
    if st.button("Spremi novu lozinku"):
        with sqlite3.connect(DB_FILE) as db:
            db.execute("UPDATE users SET password=? WHERE username=? AND company_id=?", 
                       (make_hashes(new_pass), user_to_reset, company_id))
        st.success(f"Lozinka za {user_to_reset} je uspješno resetirana!")
        log_action(st.session_state['username'], "PASSWORD_RESET", f"Reset za {user_to_reset}", company_id)

    conn.close()