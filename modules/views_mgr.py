import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import time
import sqlite3
from datetime import datetime, date
import streamlit.components.v1 as components

# Importi iz baze i utils modula
from modules.database import get_connection, get_active_period_info, DB_FILE
from modules.utils import (
    METRICS, calculate_category, render_metric_input, 
    table_to_json_string, get_df_from_json, make_hashes
)

def render_manager_view():
    conn = sqlite3.connect(DB_FILE)
    current_period, _ = get_active_period_info()
    username = st.session_state.get('username')
    company_id = st.session_state.get('company_id', 1)
    
    menu = st.sidebar.radio("Izbornik", ["📊 Dashboard", "🎯 Moji Ciljevi", "📝 Unos Procjena", "🚀 Razvojni Planovi (IDP)"])

    # --- AUTOMATSKO UPRAVLJANJE STANJEM PDF-a ---
    if 'last_active_menu' not in st.session_state:
        st.session_state['last_active_menu'] = menu

    if st.session_state['last_active_menu'] != menu:
        keys_to_reset = [k for k in st.session_state.keys() if k.startswith("prt_") or k.startswith("prt_eval_")]
        for k in keys_to_reset:
            st.session_state[k] = False
        st.session_state['last_active_menu'] = menu

    # ------------------------------------------------------------------
    # 1. DASHBOARD (Sve metrike i 9-Box)
    # ------------------------------------------------------------------
    if menu == "📊 Dashboard":
        st.header(f"📊 Moj Dashboard - {current_period}")
        my_evals = pd.read_sql_query("SELECT * FROM evaluations WHERE period=? AND manager_id=? AND company_id=?", conn, params=(current_period, username, company_id))
        my_team = pd.read_sql_query("SELECT * FROM employees_master WHERE manager_id=? AND company_id=?", conn, params=(username, company_id))
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Moj Tim", len(my_team))
        submitted_count = len(my_evals[my_evals['status'].astype(str).str.strip() == 'Submitted']) if not my_evals.empty else 0
        c2.metric("Završene Procjene", f"{submitted_count} / {len(my_team)}")
        c3.metric("Prosjek Tima", f"{my_evals['avg_performance'].mean():.2f}" if not my_evals.empty else "0.0")
        
        t1, t2 = st.tabs(["9-Box Matrica", "Povijest Zaposlenika"])
        with t1:
            if not my_evals.empty:
                fig = px.scatter(my_evals, x="avg_performance", y="avg_potential", color="category", hover_data=["ime_prezime"], range_x=[0.5,5.5], range_y=[0.5,5.5], title="Moj Tim: 9-Box")
                fig.add_hline(y=3.0, line_dash="dot"); fig.add_vline(x=3.0, line_dash="dot")
                st.plotly_chart(fig, use_container_width=True)
            else: st.info("Još nema unesenih procjena.")

    # ------------------------------------------------------------------
    # 2. MOJI CILJEVI (Identično slici image_1d8567.png)
    # ------------------------------------------------------------------
    elif menu == "🎯 Moji Ciljevi":
        st.header(f"🎯 Moji Ciljevi - {current_period}")
        m = pd.read_sql_query("SELECT * FROM employees_master WHERE company_id=?", conn, params=(company_id,))
        
        with st.expander("➕ Novi Cilj"):
            q = st.text_input("Traži zaposlenika:", placeholder="Ime...")
            if q:
                res = m[m['ime_prezime'].str.contains(q, case=False)]
                s = st.selectbox("Odaberi:", res.apply(lambda x: f"{x['ime_prezime']} ({x['kadrovski_broj']})", axis=1)) if not res.empty else None
                if s:
                    kid = s.split("(")[1].replace(")", "")
                    with st.form("ng_form"):
                        t = st.text_input("Naziv cilja")
                        w = st.number_input("Težina", 1, 100, 25)
                        ds = st.text_area("Opis")
                        dl = st.date_input("Rok")
                        if st.form_submit_button("Kreiraj"):
                            with sqlite3.connect(DB_FILE) as c_conn:
                                c_conn.execute("INSERT INTO goals (period, kadrovski_broj, manager_id, title, description, weight, progress, status, last_updated, deadline, company_id) VALUES (?,?,?,?,?,?,0,'On Track',?,?,?)", (current_period, kid, username, t, ds, w, datetime.now().strftime("%Y-%m-%d"), str(dl), company_id))
                            st.success("Cilj kreiran!"); st.rerun()

        st.markdown("---")
        # Prikaz KPI tablice
        sel_emp_goal = st.selectbox("Odaberi zaposlenika za pregled ciljeva:", ["---"] + m['ime_prezime'].tolist())
        if sel_emp_goal != "---":
            eid = m[m['ime_prezime'] == sel_emp_goal]['kadrovski_broj'].values[0]
            df_g = pd.read_sql_query("SELECT id, title as 'Cilj', description as 'KPI/Opis', weight as 'Težina %', progress as 'Ispunjenje %' FROM goals WHERE kadrovski_broj=? AND period=? AND company_id=?", conn, params=(eid, current_period, company_id))
            
            if not df_g.empty:
                edited_g = st.data_editor(df_g, key=f"ge_{eid}", num_rows="dynamic", use_container_width=True)
                if st.button("💾 SPREMI CILJEVE"):
                    with sqlite3.connect(DB_FILE) as s_conn:
                        for _, row in edited_g.iterrows():
                            s_conn.execute("UPDATE goals SET title=?, description=?, weight=?, progress=? WHERE id=?", (row['Cilj'], row['KPI/Opis'], row['Težina %'], row['Ispunjenje %'], row['id']))
                    st.toast("Spremljeno!", icon="✅"); st.rerun()

    # ------------------------------------------------------------------
    # 3. UNOS PROCJENA (Identično slici image_2ac34c.png)
    # ------------------------------------------------------------------
    elif menu == "📝 Unos Procjena":
        st.header("📝 Procjena Zaposlenika")
        my_team = pd.read_sql_query("SELECT * FROM employees_master WHERE manager_id=? AND company_id=?", conn, params=(username, company_id))
        
        for _, emp in my_team.iterrows():
            kid = emp['kadrovski_broj']
            exist = pd.read_sql_query("SELECT * FROM evaluations WHERE kadrovski_broj=? AND period=? AND is_self_eval=0 AND company_id=?", conn, params=(kid, current_period, company_id))
            r = exist.iloc[0] if not exist.empty else None
            
            with st.expander(f"👤 {emp['ime_prezime']}"):
                with st.form(f"eval_form_{kid}"):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.write("### Učinak")
                        # Koristimo METRICS rječnik za renderiranje kartica s opisima
                        p1 = render_metric_input(METRICS["p"][0], f"p1_{kid}", r['p1'] if r else 3)
                        p2 = render_metric_input(METRICS["p"][1], f"p2_{kid}", r['p2'] if r else 3)
                        p3 = render_metric_input(METRICS["p"][2], f"p3_{kid}", r['p3'] if r else 3)
                        p4 = render_metric_input(METRICS["p"][3], f"p4_{kid}", r['p4'] if r else 3)
                        p5 = render_metric_input(METRICS["p"][4], f"p5_{kid}", r['p5'] if r else 3)
                    
                    with c2:
                        st.write("### Potencijal")
                        pot1 = render_metric_input(METRICS["pot"][0], f"pot1_{kid}", r['pot1'] if r else 3, "pot")
                        pot2 = render_metric_input(METRICS["pot"][1], f"pot2_{kid}", r['pot2'] if r else 3, "pot")
                        pot3 = render_metric_input(METRICS["pot"][2], f"pot3_{kid}", r['pot3'] if r else 3, "pot")
                        pot4 = render_metric_input(METRICS["pot"][3], f"pot4_{kid}", r['pot4'] if r else 3, "pot")
                        pot5 = render_metric_input(METRICS["pot"][4], f"pot5_{kid}", r['pot5'] if r else 3, "pot")
                    
                    plan = st.text_area("Napomena / Akcijski plan:", r['action_plan'] if r else "")
                    if st.form_submit_button("💾 Spremi Procjenu"):
                        avg_p = (p1+p2+p3+p4+p5)/5
                        avg_pot = (pot1+pot2+pot3+pot4+pot5)/5
                        cat = calculate_category(avg_p, avg_pot)
                        with sqlite3.connect(DB_FILE) as ev_conn:
                            ev_conn.execute("DELETE FROM evaluations WHERE kadrovski_broj=? AND period=? AND is_self_eval=0", (kid, current_period))
                            ev_conn.execute("INSERT INTO evaluations (period, kadrovski_broj, ime_prezime, radno_mjesto, department, manager_id, p1,p2,p3,p4,p5, pot1,pot2,pot3,pot4,pot5, avg_performance, avg_potential, category, action_plan, status, company_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (current_period, kid, emp['ime_prezime'], emp['radno_mjesto'], emp['department'], username, p1,p2,p3,p4,p5, pot1,pot2,pot3,pot4,pot5, avg_p, avg_pot, cat, plan, 'Draft', company_id))
                        st.success("Spremljeno!"); st.rerun()

    # ------------------------------------------------------------------
    # 4. IDP (Identično slici image_2ac38b.png)
    # ------------------------------------------------------------------
    elif menu == "🚀 Razvojni Planovi (IDP)":
        st.header("🚀 Individualni Razvojni Planovi (IDP)")
        team = pd.read_sql_query("SELECT * FROM employees_master WHERE manager_id=? AND company_id=?", conn, params=(username, company_id))
        sel = st.selectbox("IDP za:", team['ime_prezime'].tolist())
        
        if sel:
            eid = team[team['ime_prezime']==sel]['kadrovski_broj'].values[0]
            res = conn.execute("SELECT * FROM development_plans WHERE kadrovski_broj=? AND period=? AND company_id=?", (eid, current_period, company_id)).fetchone()
            cols = [c[1] for c in conn.execute("PRAGMA table_info(development_plans)").fetchall()]
            d = dict(zip(cols, res)) if res else {}

            st.markdown("### 1. DIJAGNOZA")
            s = st.text_area("Ključne snage (Što zadržati?)", d.get('strengths',''), key=f"s_{eid}")
            w = st.text_area("Područja za razvoj (Što popraviti?)", d.get('areas_improve',''), key=f"w_{eid}")
            g = st.text_input("Karijerni cilj (1-2 godine)", d.get('career_goal',''), key=f"g_{eid}")
            
            st.markdown("### 2. PLAN AKTIVNOSTI (70-20-10)")
            
            st.write("**A) 70% ISKUSTVO I PRAKSA**")
            st.caption("Učenje kroz rad – novi zadaci, projekti, rotacije poslova.")
            # TABLICA S TOČNIM STUPCIMA: Što razviti?, Aktivnost, Rok, Dokaz
            df70 = get_df_from_json(d.get('json_70',''), ["Što razviti?", "Aktivnost", "Rok", "Dokaz"])
            d70 = st.data_editor(df70, key=f"d70_{eid}", num_rows="dynamic", use_container_width=True)
            
            st.write("**B) 20% UČENJE OD DRUGIH**")
            st.caption("Mentoring, feedback, shadowing.")
            df20 = get_df_from_json(d.get('json_20',''), ["Što razviti?", "Aktivnost", "Rok"])
            d20 = st.data_editor(df20, key=f"d20_{eid}", num_rows="dynamic", use_container_width=True)
            
            st.write("**C) 10% FORMALNA EDUKACIJA**")
            st.caption("Tečajevi, knjige, seminari.")
            df10 = get_df_from_json(d.get('json_10',''), ["Edukacija", "Trošak", "Rok"])
            d10 = st.data_editor(df10, key=f"d10_{eid}", num_rows="dynamic", use_container_width=True)
            
            if st.button("💾 SPREMI KOMPLETAN IDP", key=f"save_idp_{eid}"):
                with sqlite3.connect(DB_FILE) as idp_conn:
                    idp_conn.execute("DELETE FROM development_plans WHERE kadrovski_broj=? AND period=?", (eid, current_period))
                    idp_conn.execute("INSERT INTO development_plans (period, kadrovski_broj, manager_id, strengths, areas_improve, career_goal, json_70, json_20, json_10, status, company_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)", (current_period, eid, username, s, w, g, table_to_json_string(d70), table_to_json_string(d20), table_to_json_string(d10), "Active", company_id))
                st.toast("IDP Spremljen!", icon="✅"); time.sleep(1); st.rerun()

    conn.close()