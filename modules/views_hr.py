import streamlit as st
import pandas as pd
import plotly.express as px
import io
import sqlite3
from datetime import datetime, date
from modules.database import get_connection, get_active_period_info, DB_FILE
from modules.utils import get_df_from_json, make_hashes

def clean_excel_id(value):
    if pd.isna(value) or str(value).lower() in ['nan', 'none', '', ' ']: return ""
    str_val = str(value).strip()
    return str_val[:-2] if str_val.endswith(".0") else str_val

def render_hr_view():
    conn = get_connection()
    current_period, deadline = get_active_period_info()
    company_id = st.session_state.get('company_id', 1)
    
    # --- DOHVAT PODATAKA ---
    query_master = """
        SELECT e.kadrovski_broj, e.ime_prezime, e.radno_mjesto, e.department, 
               m.ime_prezime as 'Nadređeni Manager', e.is_manager, e.active, e.manager_id
        FROM employees_master e
        LEFT JOIN employees_master m ON e.manager_id = m.kadrovski_broj
        WHERE e.company_id = ?
    """
    df_master = pd.read_sql_query(query_master, conn, params=(company_id,))
    
    dept_list = ["Svi"]
    if not df_master.empty and 'department' in df_master.columns:
        unique_depts = df_master['department'].dropna().unique().tolist()
        dept_list += sorted(unique_depts)
    
    menu = st.sidebar.radio("HR Navigacija", [
        "📊 HR Dashboard", 
        "👤 Snail Trail (Povijest)",
        "🎯 Upravljanje Ciljevima", 
        "🚀 Razvojni Planovi (IDP)", 
        "🗂️ Šifarnik & Unos", 
        "🛠️ Admin Panel (Uređivanje)", 
        "⚙️ Postavke Razdoblja", 
        "📥 Export"
    ])

    # --- 1. DASHBOARD ---
    if menu == "📊 HR Dashboard":
        st.header(f"📊 HR Analitika - {current_period}")
        # POPRAVLJENO: Dohvaćamo i is_self_eval da razlikujemo procjene
        df_ev = pd.read_sql_query("""
            SELECT ev.kadrovski_broj, ev.ime_prezime, ev.avg_performance, ev.avg_potential, ev.category, ev.is_self_eval, em.department 
            FROM evaluations ev
            JOIN employees_master em ON ev.kadrovski_broj = em.kadrovski_broj
            WHERE ev.period = ? AND ev.company_id = ?
        """, conn, params=(current_period, company_id))
        
        df_ev['avg_performance'] = pd.to_numeric(df_ev['avg_performance'], errors='coerce').fillna(0)
        df_ev['avg_potential'] = pd.to_numeric(df_ev['avg_potential'], errors='coerce').fillna(0)
        
        # Kreiramo stupac 'Tip' za legendu grafa
        df_ev['Tip'] = df_ev['is_self_eval'].apply(lambda x: 'Samoprocjena' if x==1 else 'Službena procjena')
        
        sel_dept = st.selectbox("Filtriraj po odjelu:", dept_list)
        if sel_dept != "Svi":
            f_ev = df_ev[df_ev['department'].astype(str).str.strip() == str(sel_dept).strip()]
        else:
            f_ev = df_ev
        
        if not f_ev.empty:
            # POPRAVLJENO: Boja prema Tipu procjene i 9 polja matrice
            fig = px.scatter(f_ev, x="avg_performance", y="avg_potential", color="Tip",
                             hover_data=["ime_prezime", "category"], text="ime_prezime", 
                             range_x=[0, 5.5], range_y=[0, 5.5], title="9-Box (Usporedba)")
            
            # Linije za 9 polja
            fig.add_vline(x=2.5, line_dash="dot", line_color="gray"); fig.add_vline(x=4.0, line_dash="dot", line_color="gray")
            fig.add_hline(y=2.5, line_dash="dot", line_color="gray"); fig.add_hline(y=4.0, line_dash="dot", line_color="gray")
            
            st.plotly_chart(fig, use_container_width=True)
        else: st.warning(f"Nema podataka za odjel: {sel_dept}")

    # --- 2. SNAIL TRAIL ---
    elif menu == "👤 Snail Trail (Povijest)":
        st.header("👤 Povijesni razvoj")
        sel_emp = st.selectbox("Djelatnik:", [f"{r['ime_prezime']} ({r['kadrovski_broj']})" for _, r in df_master.iterrows()])
        if sel_emp:
            eid = sel_emp.split("(")[1].replace(")", "")
            h = pd.read_sql_query("SELECT period, avg_performance, avg_potential, category, is_self_eval FROM evaluations WHERE kadrovski_broj=? ORDER BY period ASC", conn, params=(eid,))
            if not h.empty:
                h['Izvor'] = h['is_self_eval'].apply(lambda x: 'Samoprocjena' if x==1 else 'Voditelj')
                st.plotly_chart(px.line(h, x="period", y=["avg_performance", "avg_potential"], color="Izvor", markers=True), use_container_width=True)
                st.table(h)
            else: st.info("Nema povijesti.")

    # --- 3. CILJEVI ---
    elif menu == "🎯 Upravljanje Ciljevima":
        st.header("🎯 Detaljni pregled ciljeva")
        f_dept = st.selectbox("Odjel:", dept_list, key="g_dept")
        f_master = df_master if f_dept == "Svi" else df_master[df_master['department'] == f_dept]
        for _, emp in f_master.iterrows():
            eid = emp['kadrovski_broj']
            goals = pd.read_sql_query("SELECT * FROM goals WHERE kadrovski_broj=? AND period=?", conn, params=(eid, current_period))
            if not goals.empty:
                with st.expander(f"👤 {emp['ime_prezime']} ({len(goals)} ciljeva)"):
                    for _, g in goals.iterrows():
                        st.write(f"**{g['title']}** ({g['weight']}%) - `{g['status']}`")
                        st.progress(float(g['progress'])/100 if g['progress'] else 0.0)
                        kpis = pd.read_sql_query("SELECT description, weight, progress FROM goal_kpis WHERE goal_id=?", conn, params=(g['id'],))
                        if not kpis.empty: st.dataframe(kpis, use_container_width=True, hide_index=True)

    # --- 4. RAZVOJNI PLANOVI ---
    elif menu == "🚀 Razvojni Planovi (IDP)":
        st.header("🚀 Puni IDP Obrazac")
        f_dept = st.selectbox("Odjel:", dept_list, key="idp_f")
        f_m = df_master if f_dept == "Svi" else df_master[df_master['department'] == f_dept]
        for _, emp in f_m.iterrows():
            eid = emp['kadrovski_broj']
            res = conn.execute("SELECT * FROM development_plans WHERE kadrovski_broj=? AND period=?", (eid, current_period)).fetchone()
            tag = "✅ ISPUNJEN" if res else "❌ NEDOSTAJE"
            with st.expander(f"{tag} | {emp['ime_prezime']} ({emp['radno_mjesto']})"):
                if res:
                    cols = [c[1] for c in conn.execute("PRAGMA table_info(development_plans)").fetchall()]
                    d = dict(zip(cols, res))
                    st.subheader("1. Dijagnoza i Karijerni cilj")
                    st.write(f"**Glavni karijerni cilj:** {d.get('career_goal')}")
                    c1, c2 = st.columns(2)
                    c1.info(f"**Snage:**\n\n{d.get('strengths')}")
                    c2.warning(f"**Područja za razvoj:**\n\n{d.get('areas_improve')}")
                    st.subheader("2. Akcijski plan")
                    st.write("**70% Iskustvo:**"); st.dataframe(get_df_from_json(d.get('json_70'), ["Što?", "Aktivnost", "Rok", "Dokaz"]), use_container_width=True)
                    st.write("**20% Mentoring:**"); st.dataframe(get_df_from_json(d.get('json_20'), ["Što?", "Aktivnost", "Rok"]), use_container_width=True)
                    st.write("**10% Edukacija:**"); st.dataframe(get_df_from_json(d.get('json_10'), ["Edukacija", "Trošak", "Rok"]), use_container_width=True)
                    st.subheader("3. Podrška")
                    st.success(f"**Potrebno:** {d.get('support_needed')}")
                else: st.info("IDP nije kreiran.")

    # --- 5. ŠIFARNIK & UNOS ---
    elif menu == "🗂️ Šifarnik & Unos":
        st.header("🗂️ Upravljanje Zaposlenicima")
        t1, t2, t3 = st.tabs(["📋 Popis", "➕ Ručni Unos", "📥 Excel Import"])
        with t1:
            st.dataframe(df_master.drop(columns=['manager_id'], errors='ignore'), use_container_width=True)
        with t2:
            with st.form("manual_add"):
                c1, c2 = st.columns(2)
                kb = c1.text_input("Kadrovski broj*")
                ip = c2.text_input("Ime i Prezime*")
                rm = c1.text_input("Radno mjesto")
                od = c2.text_input("Odjel")
                mgr_ops = {f"{r['ime_prezime']}": r['kadrovski_broj'] for _, r in df_master[df_master['is_manager']==1].iterrows()}
                sel_m = st.selectbox("Procjenitelj:", ["---"] + list(mgr_ops.keys()))
                is_m = st.radio("Procjenitelj (ima tim)?", ["NE", "DA"], horizontal=True)
                if st.form_submit_button("Spremi"):
                    if kb and ip:
                        with sqlite3.connect(DB_FILE) as db:
                            db.execute("INSERT INTO employees_master (kadrovski_broj, ime_prezime, radno_mjesto, department, manager_id, is_manager, active, company_id) VALUES (?,?,?,?,?,?,?,?)",
                                       (kb, ip, rm, od, mgr_ops.get(sel_m, ""), 1 if is_m == "DA" else 0, 1, company_id))
                            db.execute("INSERT OR REPLACE INTO users (username, password, role, department, company_id) VALUES (?,?,?,?,?)",
                                       (kb, make_hashes("lozinka123"), "Manager" if is_m == "DA" else "Employee", od, company_id))
                        st.success("Dodan!"); st.rerun()
        with t3:
            f = st.file_uploader("Excel file", type=['xlsx'])
            if f and st.button("Pokreni Import"):
                try:
                    df_i = pd.read_excel(f)
                    with sqlite3.connect(DB_FILE) as db:
                        for _, r in df_i.iterrows():
                            kid = clean_excel_id(r['kadrovski_broj'])
                            mgr_id_val = clean_excel_id(r['manager_id']) if 'manager_id' in r else ""
                            is_mgr_val = 1 if str(r.get('is_manager','')).upper()=='DA' else 0
                            db.execute("INSERT OR REPLACE INTO employees_master (kadrovski_broj, ime_prezime, radno_mjesto, department, manager_id, is_manager, active, company_id) VALUES (?,?,?,?,?,?,?,?)",
                                    (kid, r['ime_prezime'], r['radno_mjesto'], r['department'], mgr_id_val, is_mgr_val, 1, company_id))
                            db.execute("INSERT OR IGNORE INTO users (username, password, role, department, company_id) VALUES (?,?,?,?,?)",
                                    (kid, make_hashes("lozinka123"), "Manager" if is_mgr_val == 1 else "Employee", r['department'], company_id))
                    st.success("Import završen!"); st.rerun()
                except Exception as e: st.error(f"Greška: {e}")

    # --- 6. ADMIN PANEL ---
    elif menu == "🛠️ Admin Panel (Uređivanje)":
        st.header("🛠️ Uređivanje podataka")
        sel_e = st.selectbox("Djelatnik:", ["---"] + [f"{r['ime_prezime']} ({r['kadrovski_broj']})" for _, r in df_master.iterrows()])
        if sel_e != "---":
            eid = sel_e.split("(")[1].replace(")", "")
            curr = df_master[df_master['kadrovski_broj'] == eid].iloc[0]
            with st.form("admin_edit"):
                c1, c2 = st.columns(2)
                n_ime = c1.text_input("Ime", value=curr['ime_prezime'])
                n_odjel = c2.text_input("Odjel", value=curr['department'])
                n_pw = c1.text_input("Reset lozinke", type="password")
                if st.form_submit_button("Spremi"):
                    with sqlite3.connect(DB_FILE) as db:
                        db.execute("UPDATE employees_master SET ime_prezime=?, department=? WHERE kadrovski_broj=?", (n_ime, n_odjel, eid))
                        if n_pw: db.execute("UPDATE users SET password=? WHERE username=?", (make_hashes(n_pw), eid))
                    st.success("Spremljeno!"); st.rerun()

    # --- 7. POSTAVKE RAZDOBLJA (POPRAVLJENO RUŠENJE) ---
    elif menu == "⚙️ Postavke Razdoblja":
        st.header("⚙️ Upravljanje Ciklusima")
        t_p1, t_p2 = st.tabs(["➕ Novo Razdoblje", "📅 Uredi Rok"])
        with t_p1:
            p_n = st.text_input("Naziv (npr. 2026-H2)")
            p_d = st.date_input("Krajnji rok")
            if st.button("Aktiviraj"):
                with sqlite3.connect(DB_FILE) as db:
                    db.execute("INSERT OR REPLACE INTO periods (period_name, deadline, company_id) VALUES (?,?,?)", (p_n, str(p_d), company_id))
                    db.execute("UPDATE app_settings SET setting_value=? WHERE setting_key='active_period'", (p_n,))
                st.success("Aktivirano!"); st.rerun()
        with t_p2:
            st.write(f"Trenutno aktivno: {current_period} (Rok: {deadline})")
            try:
                initial_val = datetime.strptime(str(deadline), '%Y-%m-%d').date()
            except:
                initial_val = date.today()
            new_deadline = st.date_input("Novi rok", value=initial_val)
            if st.button("Spremi"):
                conn.execute("UPDATE periods SET deadline=? WHERE period_name=?", (str(new_deadline), current_period))
                conn.commit(); st.success("Spremljeno!"); st.rerun()

    # --- 8. EXPORT ---
    elif menu == "📥 Export":
        st.header("📥 Export")
        if st.button("Generiraj Excel"):
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                for t in ["employees_master", "evaluations", "users", "goals", "development_plans", "delegated_tasks"]:
                    try: pd.read_sql_query(f"SELECT * FROM {t} WHERE company_id={company_id}", conn).to_excel(writer, sheet_name=t[:31], index=False)
                    except: pass
            st.download_button("Preuzmi .xlsx", buffer.getvalue(), f"Export_{date.today()}.xlsx")

    conn.close()