import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import time
import sqlite3
from datetime import datetime, date
import streamlit.components.v1 as components

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
    
    menu = st.sidebar.radio("Izbornik", ["📊 Dashboard", "🎯 Moji Ciljevi", "📝 Unos Procjena", "🚀 Razvojni Planovi (IDP)", "🤝 Upravljanje Ljudima"])

    if 'last_active_menu' not in st.session_state: st.session_state['last_active_menu'] = menu
    if st.session_state['last_active_menu'] != menu:
        keys_to_reset = [k for k in st.session_state.keys() if k.startswith("prt_") or k.startswith("prt_eval_")]
        for k in keys_to_reset: st.session_state[k] = False
        st.session_state['last_active_menu'] = menu

    # 1. DASHBOARD
    if menu == "📊 Dashboard":
        st.header(f"📊 Moj Dashboard - {current_period}")
        my_evals = pd.read_sql_query("SELECT * FROM evaluations WHERE period=? AND manager_id=? AND company_id=? AND is_self_eval=0", conn, params=(current_period, username, company_id))
        my_team = pd.read_sql_query("SELECT * FROM employees_master WHERE manager_id=? AND company_id=?", conn, params=(username, company_id))
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Moj Tim", len(my_team))
        submitted_count = len(my_evals[my_evals['status'].astype(str).str.strip() == 'Submitted']) if not my_evals.empty else 0
        c2.metric("Završene Procjene", f"{submitted_count} / {len(my_team)}")
        c3.metric("Prosjek Tima", f"{my_evals['avg_performance'].mean():.2f}" if not my_evals.empty else "0.0")
        
        t1, t2, t3 = st.tabs(["9-Box Matrica", "Povijest Zaposlenika", "🤝 Delegiranje"])
        with t1:
            if not my_evals.empty:
                fig = px.scatter(my_evals, x="avg_performance", y="avg_potential", color="category", hover_data=["ime_prezime"], range_x=[0.5,5.5], range_y=[0.5,5.5], title="Moj Tim: 9-Box")
                fig.add_hline(y=3.0, line_dash="dot"); fig.add_vline(x=3.0, line_dash="dot")
                st.plotly_chart(fig, use_container_width=True)
            else: st.info("Još nema unesenih procjena.")
        
        with t2:
            if not my_team.empty:
                sel_emp = st.selectbox("Odaberi zaposlenika:", my_team['ime_prezime'].tolist())
                if sel_emp:
                    kid = my_team[my_team['ime_prezime']==sel_emp]['kadrovski_broj'].values[0]
                    hist = pd.read_sql_query("SELECT period, avg_performance, avg_potential, category FROM evaluations WHERE kadrovski_broj=? AND is_self_eval=0 ORDER BY period", conn, params=(kid,))
                    if not hist.empty:
                        fig_l = px.line(hist, x="period", y=["avg_performance", "avg_potential"], markers=True, range_y=[0, 6])
                        st.plotly_chart(fig_l, use_container_width=True)
                        st.table(hist)

        with t3:
            st.subheader("🤝 Delegiranje procjene")
            with st.form("delegate_f"):
                delegate = st.selectbox("Mentor/Senior koji ocjenjuje:", my_team['ime_prezime'].tolist())
                target = st.selectbox("Zaposlenik koga treba ocijeniti:", my_team['ime_prezime'].tolist())
                if st.form_submit_button("Potvrdi delegaciju"):
                    del_id = my_team[my_team['ime_prezime']==delegate]['kadrovski_broj'].values[0]
                    tar_id = my_team[my_team['ime_prezime']==target]['kadrovski_broj'].values[0]
                    conn.execute("INSERT INTO delegated_tasks (manager_id, delegate_id, target_id, period, status, company_id) VALUES (?,?,?,?,'Pending',?)", (username, del_id, tar_id, current_period, company_id))
                    conn.commit(); st.success("Delegirano!")
            
            st.divider()
            st.write("### Povijest delegiranja")
            query_del = """
                SELECT e_target.ime_prezime as 'Zaposlenik', 
                       e_delegate.ime_prezime as 'Mentor/Senior', 
                       d.status as 'Status'
                FROM delegated_tasks d
                JOIN employees_master e_target ON d.target_id = e_target.kadrovski_broj
                JOIN employees_master e_delegate ON d.delegate_id = e_delegate.kadrovski_broj
                WHERE d.manager_id = ? AND d.company_id = ?
            """
            del_hist = pd.read_sql_query(query_del, conn, params=(username, company_id))
            st.dataframe(del_hist, use_container_width=True, hide_index=True)

    # 2. MOJI CILJEVI
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
                            conn.execute("INSERT INTO goals (period, kadrovski_broj, manager_id, title, description, weight, progress, status, last_updated, deadline, company_id) VALUES (?,?,?,?,?,?,0,'On Track',?,?,?)", (current_period, kid, username, t, ds, w, datetime.now().strftime("%Y-%m-%d"), str(dl), company_id))
                            conn.commit(); st.success("Cilj kreiran!"); st.rerun()

        st.markdown("---")
        my_team_goals = pd.read_sql_query("SELECT * FROM employees_master WHERE manager_id=? AND company_id=?", conn, params=(username, company_id))
        
        for _, r in my_team_goals.iterrows():
            eid = r['kadrovski_broj']
            goals = pd.read_sql_query("SELECT * FROM goals WHERE kadrovski_broj=? AND period=? AND company_id=?", conn, params=(eid, current_period, company_id))
            
            with st.expander(f"👤 {r['ime_prezime']} (Ciljevi: {len(goals)})"):
                for _, g in goals.iterrows():
                    gid = g['id']
                    st.markdown(f"**{g['title']} ({g['weight']}%)**")
                    kpis = pd.read_sql_query("SELECT description, weight, progress, deadline FROM goal_kpis WHERE goal_id=?", conn, params=(gid,))
                    df_k = kpis.rename(columns={'description':'KPI','weight':'Težina','progress':'%','deadline':'Rok'}) if not kpis.empty else pd.DataFrame(columns=['KPI','Težina','%','Rok'])
                    ed = st.data_editor(df_k, key=f"k_{gid}", num_rows="dynamic", use_container_width=True)
                    if st.button("💾 Spremi KPI", key=f"s_{gid}"):
                        calc = (pd.to_numeric(ed['Težina'], errors='coerce').fillna(0) * pd.to_numeric(ed['%'], errors='coerce').fillna(0)).sum() / 100
                        conn.execute("UPDATE goals SET progress=?, last_updated=? WHERE id=?", (calc, datetime.now().strftime("%Y-%m-%d"), gid))
                        conn.execute("DELETE FROM goal_kpis WHERE goal_id=?", (gid,))
                        for _, kr in ed.iterrows():
                            if str(kr['KPI']).strip(): conn.execute("INSERT INTO goal_kpis (goal_id, description, weight, progress, deadline) VALUES (?,?,?,?,?)", (gid, str(kr['KPI']), str(kr['Težina']), str(kr['%']), str(kr['Rok'])))
                        conn.commit(); st.toast("Spremljeno!", icon="✅"); st.rerun()

    # 3. UNOS PROCJENA
    elif menu == "📝 Unos Procjena":
        st.header("📝 Procjena Zaposlenika")
        my_team = pd.read_sql_query("SELECT * FROM employees_master WHERE manager_id=? AND company_id=?", conn, params=(username, company_id))
        
        for _, emp in my_team.iterrows():
            kid = emp['kadrovski_broj']
            exist = pd.read_sql_query("SELECT * FROM evaluations WHERE kadrovski_broj=? AND period=? AND is_self_eval=0 AND company_id=?", conn, params=(kid, current_period, company_id))
            s_eval = pd.read_sql_query("SELECT * FROM evaluations WHERE kadrovski_broj=? AND period=? AND is_self_eval=1 AND company_id=?", conn, params=(kid, current_period, company_id))
            
            r = exist.iloc[0] if not exist.empty else None
            is_locked = not exist.empty and str(exist.iloc[0]['status']).strip() == 'Submitted'
            
            with st.expander(f"{'🔒' if is_locked else '✏️'} {emp['ime_prezime']}"):
                if not s_eval.empty:
                    st.info("💡 Samoprocjena zaposlenika:")
                    se = s_eval.iloc[0]
                    gap_data = {
                        "Metrika": [m['label'] for m in METRICS["p"]] + [m['label'] for m in METRICS["pot"]],
                        "Zaposlenik": [se['p1'], se['p2'], se['p3'], se['p4'], se['p5'], se['pot1'], se['pot2'], se['pot3'], se['pot4'], se['pot5']],
                        "Manager": [r['p1'] if r else 0, r['p2'] if r else 0, r['p3'] if r else 0, r['p4'] if r else 0, r['p5'] if r else 0, r['pot1'] if r else 0, r['pot2'] if r else 0, r['pot3'] if r else 0, r['pot4'] if r else 0, r['pot5'] if r else 0]
                    }
                    st.dataframe(pd.DataFrame(gap_data), use_container_width=True)

                if is_locked and r is not None:
                    st.success("Procjena zaključana.")
                    c1, c2 = st.columns(2)
                    with c1:
                        st.write("**Učinak:**")
                        for i, m in enumerate(METRICS["p"]): st.write(f"{m['label']}: {r[f'p{i+1}']}")
                    with c2:
                        st.write("**Potencijal:**")
                        for i, m in enumerate(METRICS["pot"]): st.write(f"{m['label']}: {r[f'pot{i+1}']}")
                    
                    if st.button("🖨️ PDF Procjene", key=f"pdf_{kid}"):
                        html_pdf = f"""<html><head><style>body {{ font-family: sans-serif; }}</style></head><body>
                        <h1>Procjena: {emp['ime_prezime']}</h1><p>Kategorija: <b>{r['category']}</b></p>
                        <h3>Učinak</h3><ul>{"".join([f"<li>{METRICS['p'][i]['label']}: {r[f'p{i+1}']}</li>" for i in range(5)])}</ul>
                        <h3>Potencijal</h3><ul>{"".join([f"<li>{METRICS['pot'][i]['label']}: {r[f'pot{i+1}']}</li>" for i in range(5)])}</ul>
                        <p><b>Akcijski plan:</b> {r['action_plan']}</p><script>window.print();</script></body></html>"""
                        components.html(html_pdf, height=500, scrolling=True)
                else:
                    with st.form(f"eval_form_{kid}"):
                        c1, c2 = st.columns(2)
                        with c1:
                            p = [render_metric_input(METRICS["p"][i], f"p{i}_{kid}", r[f'p{i+1}'] if r is not None else 3) for i in range(5)]
                        with c2:
                            pot = [render_metric_input(METRICS["pot"][i], f"pot{i}_{kid}", r[f'pot{i+1}'] if r is not None else 3, "pot") for i in range(5)]
                        plan = st.text_area("Bilješke:", r['action_plan'] if r is not None else "")
                        
                        if st.form_submit_button("💾 Spremi Procjenu"):
                            ap, at = sum(p)/5, sum(pot)/5
                            cat = calculate_category(ap, at)
                            conn.execute("DELETE FROM evaluations WHERE kadrovski_broj=? AND period=? AND is_self_eval=0", (kid, current_period))
                            conn.execute("""INSERT INTO evaluations 
                                (period, kadrovski_broj, ime_prezime, radno_mjesto, department, manager_id, 
                                p1, p2, p3, p4, p5, pot1, pot2, pot3, pot4, pot5, 
                                avg_performance, avg_potential, category, action_plan, status, feedback_date, company_id, is_self_eval) 
                                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", 
                                (current_period, kid, emp['ime_prezime'], emp['radno_mjesto'], emp['department'], username,
                                 *p, *pot, ap, at, cat, plan, 'Submitted', datetime.now().strftime("%Y-%m-%d"), company_id, 0))
                            conn.commit(); st.success("Spremljeno!"); st.rerun()
                    
                    if r is not None:
                        lock = st.checkbox("Potvrđujem konačnost procjene", key=f"lock_{kid}")
                        if st.button("🔒 ZAKLJUČAJ", disabled=not lock, type="primary"):
                            conn.execute("UPDATE evaluations SET status='Submitted' WHERE id=?", (int(r['id']),))
                            conn.commit(); st.rerun()

    # 4. IDP
    elif menu == "🚀 Razvojni Planovi (IDP)":
        st.header("🚀 Razvojni Planovi (IDP)")
        team = pd.read_sql_query("SELECT * FROM employees_master WHERE manager_id=? AND company_id=?", conn, params=(username, company_id))
        
        for _, emp in team.iterrows():
            eid = emp['kadrovski_broj']
            res = conn.execute("SELECT * FROM development_plans WHERE kadrovski_broj=? AND period=?", (eid, current_period)).fetchone()
            cols = [c[1] for c in conn.execute("PRAGMA table_info(development_plans)").fetchall()]
            d = dict(zip(cols, res)) if res else {}

            with st.expander(f"📄 {emp['ime_prezime']}"):
                st.markdown("### 1. DIJAGNOZA")
                s = st.text_area("Snage:", d.get('strengths',''), key=f"s_{eid}")
                w = st.text_area("Razvoj:", d.get('areas_improve',''), key=f"w_{eid}")
                g = st.text_input("Cilj:", d.get('career_goal',''), key=f"g_{eid}")
                
                st.markdown("### 2. PLAN 70-20-10")
                d70 = st.data_editor(get_df_from_json(d.get('json_70',''), ["Što razviti?", "Aktivnost", "Rok", "Dokaz"]), key=f"d70_{eid}", num_rows="dynamic", use_container_width=True)
                d20 = st.data_editor(get_df_from_json(d.get('json_20',''), ["Što razviti?", "Aktivnost", "Rok"]), key=f"d20_{eid}", num_rows="dynamic", use_container_width=True)
                d10 = st.data_editor(get_df_from_json(d.get('json_10',''), ["Edukacija", "Trošak", "Rok"]), key=f"d10_{eid}", num_rows="dynamic", use_container_width=True)
                
                st.markdown("### 3. PODRŠKA")
                sup_opts = ["Budžet", "Vrijeme", "Mentorstvo", "Alati"]
                sup_db = d.get('support_needed')
                sup_list = [x.strip() for x in sup_db.split(',') if x.strip() in sup_opts] if sup_db else []
                sup = st.multiselect("Potrebno:", sup_opts, default=sup_list, key=f"sup_{eid}")
                sup_n = st.text_input("Napomene:", d.get('support_notes',''), key=f"sn_{eid}")
                
                if st.button("💾 SPREMI IDP", key=f"save_idp_{eid}"):
                    conn.execute("DELETE FROM development_plans WHERE kadrovski_broj=? AND period=?", (eid, current_period))
                    conn.execute("INSERT INTO development_plans (period, kadrovski_broj, manager_id, strengths, areas_improve, career_goal, json_70, json_20, json_10, support_needed, support_notes, status, company_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (current_period, eid, username, s, w, g, table_to_json_string(d70), table_to_json_string(d20), table_to_json_string(d10), ",".join(sup), sup_n, "Active", company_id))
                    conn.commit(); st.toast("IDP Spremljen!", icon="✅"); st.rerun()

    # 5. UPRAVLJANJE LJUDIMA
    elif menu == "🤝 Upravljanje Ljudima":
        st.header("🤝 Upravljanje Ljudima")
        my_team = pd.read_sql_query("SELECT * FROM employees_master WHERE manager_id=?", conn, params=(username,))
        t1, t2 = st.tabs(["🙌 Pohvale", "📅 1-on-1 Sastanci"])
        with t1:
            with st.form("mgr_kudos"):
                receiver = st.selectbox("Zaposlenik:", my_team['ime_prezime'].tolist())
                msg = st.text_area("Poruka pohvale:")
                if st.form_submit_button("Pošalji"):
                    rid = my_team[my_team['ime_prezime']==receiver]['kadrovski_broj'].values[0]
                    conn.execute("INSERT INTO recognitions (sender_id, receiver_id, message, timestamp, company_id) VALUES (?,?,?,?,?)", (username, rid, msg, datetime.now().strftime("%Y-%m-%d"), company_id))
                    conn.commit(); st.success("Poslano!")
        with t2:
            with st.form("mgr_1on1"):
                receiver_1 = st.selectbox("Sastanak sa:", my_team['ime_prezime'].tolist())
                notes = st.text_area("Bilješke sa sastanka")
                if st.form_submit_button("Spremi"):
                    rid = my_team[my_team['ime_prezime']==receiver_1]['kadrovski_broj'].values[0]
                    # FIX: Insert u tablicu meeting_notes (ne meetings_1on1)
                    conn.execute("INSERT INTO meeting_notes (kadrovski_broj, manager_id, date, notes, action_items, company_id) VALUES (?,?,?,?,?,?)", (rid, username, str(date.today()), notes, "", company_id))
                    conn.commit(); st.success("Zabilježeno!")

    conn.close()