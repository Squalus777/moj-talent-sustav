import streamlit as st
import pandas as pd
import io
import time
import sqlite3
from datetime import datetime, date
from modules.database import get_connection, get_active_period_info, DB_FILE, log_action
from modules.utils import make_hashes

def render_hr_view():
    conn = get_connection()
    current_period, deadline = get_active_period_info()
    company_id = st.session_state.get('company_id', 1)
    
    # Priprema liste voditelja za izbornike
    query_mgrs = "SELECT ime_prezime, kadrovski_broj FROM employees_master WHERE is_manager = 1 AND active = 1 AND company_id = ?"
    mgr_data = pd.read_sql_query(query_mgrs, conn, params=(company_id,))
    mgr_mapping = {row['ime_prezime']: row['kadrovski_broj'] for _, row in mgr_data.iterrows()}
    mgr_display_list = ["--- Nema nadređenog ---"] + list(mgr_mapping.keys())

    menu = st.sidebar.radio("HR Navigacija", ["📊 Dashboard", "🎯 Pulse Ankete", "🏆 Kultura", "🗂️ Šifarnik & Uređivanje", "📥 Import", "⚙️ Postavke Razdoblja", "🛠️ Admin Panel", "📥 Export"])

    if menu == "🗂️ Šifarnik & Uređivanje":
        st.header("🗂️ Upravljanje Zaposlenicima")
        t1, t2, t3 = st.tabs(["📋 Popis", "➕ Novi Zaposlenik", "📝 Uredi & Aktiviraj Login"])
        
        with t1:
            df_list = pd.read_sql_query("SELECT kadrovski_broj, ime_prezime, radno_mjesto, department, is_manager, active FROM employees_master WHERE company_id=?", conn, params=(company_id,))
            st.dataframe(df_list, use_container_width=True)

        with t2:
            with st.form("new_emp_form"):
                kb = st.text_input("Kadrovski broj*")
                ip = st.text_input("Ime i Prezime*")
                rm = st.text_input("Radno mjesto")
                od = st.text_input("Odjel")
                sel_mgr = st.selectbox("Procjenitelj:", mgr_display_list)
                is_m_choice = st.radio("Ima tim za procjenu?", ["NE", "DA"], horizontal=True)
                init_pw = st.text_input("Postavi lozinku:", value="lozinka123")
                
                if st.form_submit_button("Spremi"):
                    if kb and ip:
                        m_id = mgr_mapping.get(sel_mgr, "")
                        is_m_val = 1 if is_m_choice == "DA" else 0
                        with sqlite3.connect(DB_FILE) as db:
                            db.execute("INSERT INTO employees_master (kadrovski_broj, ime_prezime, radno_mjesto, department, manager_id, company_id, is_manager, active) VALUES (?,?,?,?,?,?,?,1)", (kb, ip, rm, od, m_id, company_id, is_m_val))
                            db.execute("INSERT OR REPLACE INTO users (username, password, role, department, company_id) VALUES (?,?,?,?,?)", (kb, make_hashes(init_pw), "Manager" if is_m_val == 1 else "Employee", od, company_id))
                        st.success("Zaposlenik i račun kreirani!"); st.rerun()

        with t3:
            all_e = pd.read_sql_query("SELECT * FROM employees_master WHERE company_id=?", conn, params=(company_id,))
            e_map = {f"{r['ime_prezime']} ({r['kadrovski_broj']})": r['kadrovski_broj'] for _, r in all_e.iterrows()}
            sel_e = st.selectbox("Odaberi zaposlenika:", ["---"] + list(e_map.keys()))
            
            if sel_e != "---":
                eid = e_map[sel_e]
                curr = all_e[all_e['kadrovski_broj'] == eid].iloc[0]
                
                # Provjera postoji li račun u tablici users
                curr_user = pd.read_sql_query("SELECT * FROM users WHERE username=?", conn, params=(eid,))
                exists = not curr_user.empty

                with st.form("edit_and_fix"):
                    st.write(f"Uređivanje: **{curr['ime_prezime']}**")
                    if not exists:
                        st.warning("⚠️ Ovaj zaposlenik nema račun. Unesi lozinku ispod da ga kreiraš.")
                    
                    new_pw = st.text_input("Nova lozinka (obavezno za nove račune):", type="password")
                    n_od = st.text_input("Odjel", value=curr['department'])
                    n_is_m = st.radio("Ima tim?", ["NE", "DA"], index=int(curr['is_manager']), horizontal=True)
                    
                    if st.form_submit_button("Spremi promjene"):
                        is_m_final = 1 if n_is_m == "DA" else 0
                        role_final = "Manager" if is_m_final == 1 else "Employee"
                        with sqlite3.connect(DB_FILE) as db:
                            db.execute("UPDATE employees_master SET department=?, is_manager=? WHERE kadrovski_broj=?", (n_od, is_m_final, eid))
                            if not exists:
                                if new_pw:
                                    db.execute("INSERT INTO users (username, password, role, department, company_id) VALUES (?,?,?,?,?)", (eid, make_hashes(new_pw), role_final, n_od, company_id))
                                else: st.error("Moraš unijeti lozinku!"); st.stop()
                            else:
                                db.execute("UPDATE users SET role=?, department=? WHERE username=?", (role_final, n_od, eid))
                                if new_pw: db.execute("UPDATE users SET password=? WHERE username=?", (make_hashes(new_pw), eid))
                        st.success("Spremljeno!"); time.sleep(1); st.rerun()

    # --- OSTALI MODULI ---
    elif menu == "⚙️ Postavke Razdoblja":
        st.header("⚙️ Upravljanje Periodima")
        p_name = st.text_input("Naziv", value=current_period)
        p_date = st.date_input("Rok")
        if st.button("Aktiviraj"):
            with sqlite3.connect(DB_FILE) as db:
                db.execute("INSERT OR REPLACE INTO periods (period_name, deadline, company_id) VALUES (?,?,?)", (p_name, str(p_date), company_id))
                db.execute("UPDATE app_settings SET setting_value=? WHERE setting_key='active_period' AND company_id=?", (p_name, company_id))
            st.success("Period promijenjen!"); st.rerun()

    elif menu == "📥 Export":
        st.header("📥 Export")
        if st.button("Generiraj Excel"):
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                for t in ["employees_master", "evaluations", "users", "pulse_responses"]:
                    pd.read_sql_query(f"SELECT * FROM {t} WHERE company_id={company_id}", conn).to_excel(writer, sheet_name=t[:31], index=False)
            st.download_button("Preuzmi", buffer.getvalue(), "TalentReport.xlsx")

    conn.close()