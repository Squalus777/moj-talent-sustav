import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date
import sqlite3
from modules.database import get_connection, get_active_period_info, DB_FILE
from modules.utils import METRICS, calculate_category, render_metric_input

def render_employee_view():
    conn = get_connection()
    username = st.session_state['username']
    company_id = st.session_state['company_id']
    current_period, _ = get_active_period_info()

    # Dohvat imena za zaglavlje
    emp_res = conn.execute("SELECT ime_prezime, radno_mjesto, department FROM employees_master WHERE kadrovski_broj=?", (username,)).fetchone()
    my_name = emp_res[0] if emp_res else username
    
    st.header(f"👋 Dobrodošli, {my_name}")
    del_tasks = pd.read_sql_query("""SELECT d.*, e.ime_prezime as target_name FROM delegated_tasks d JOIN employees_master e ON d.target_id = e.kadrovski_broj WHERE d.delegate_id = ? AND d.period = ? AND d.status = 'Pending'""", conn, params=(username, current_period))

    tab_labels = ["📈 Napredak", "🎯 Ciljevi", "📝 Samoprocjena", "🙌 Pohvale & Pulse", "🤝 Moji 1-on-1"]
    if not del_tasks.empty: tab_labels.append(f"🤝 Zadaci za mene ({len(del_tasks)})")
    tabs = st.tabs(tab_labels)

    # 1. NAPREDAK
    with tabs[0]:
        st.subheader("Povijest rezultata")
        hist = pd.read_sql_query("SELECT period, avg_performance, avg_potential FROM evaluations WHERE kadrovski_broj=? AND is_self_eval=0", conn, params=(username,))
        if not hist.empty: st.plotly_chart(px.line(hist, x='period', y=['avg_performance', 'avg_potential'], markers=True), use_container_width=True)
        else: st.info("Nema povijesnih podataka.")

    # 2. CILJEVI
    with tabs[1]:
        st.subheader("Moji ciljevi")
        goals = pd.read_sql_query("SELECT title, progress, description, deadline, status FROM goals WHERE kadrovski_broj=? AND period=?", conn, params=(username, current_period))
        if not goals.empty:
            for _, g in goals.iterrows():
                st.write(f"**{g['title']}** ({g['status']})")
                st.progress(g['progress']/100)
                st.caption(f"Rok: {g['deadline']} | {g['description']}")
                st.divider()
        else: st.info("Nemate definiranih ciljeva za ovaj period.")

    # 3. SAMOPROCJENA
    with tabs[2]:
        st.subheader("Moja samoprocjena")
        with st.form("self_eval"):
            c1, c2 = st.columns(2)
            with c1: p = [render_metric_input(METRICS["p"][i], f"sp{i}", 3) for i in range(5)]
            with c2: pot = [render_metric_input(METRICS["pot"][i], f"spot{i}", 3, "pot") for i in range(5)]
            if st.form_submit_button("Spremi samoprocjenu"):
                ap, apot = sum(p)/5, sum(pot)/5
                cat = calculate_category(ap, apot)
                # Siguran dohvat podataka o zaposleniku
                if emp_res:
                    nm, rm, dp = emp_res[0], emp_res[1], emp_res[2]
                else:
                    nm, rm, dp = username, "Employee", "N/A"
                
                conn.execute("DELETE FROM evaluations WHERE kadrovski_broj=? AND period=? AND is_self_eval=1", (username, current_period))
                conn.execute("""INSERT INTO evaluations 
                    (period, kadrovski_broj, ime_prezime, radno_mjesto, department, manager_id, 
                    p1, p2, p3, p4, p5, pot1, pot2, pot3, pot4, pot5, 
                    avg_performance, avg_potential, category, action_plan, status, feedback_date, company_id, is_self_eval) 
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (current_period, username, nm, rm, dp, "Self", 
                     *p, *pot, ap, apot, cat, "", "Submitted", datetime.now().strftime("%Y-%m-%d"), company_id, 1))
                conn.commit(); st.success("Samoprocjena spremljena!"); st.rerun()

    # 4. POHVALE I PULSE
    with tabs[3]:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("🙌 Pohvale")
            kudos = pd.read_sql_query("SELECT sender_id, category, message, timestamp FROM recognitions WHERE receiver_id=? ORDER BY timestamp DESC", conn, params=(username,))
            if not kudos.empty: [st.info(f"**{k['category']}** od {k['sender_id']}\n\n{k['message']}") for _, k in kudos.iterrows()]
            else: st.write("Nema novih pohvala.")
        with c2:
            st.subheader("📊 Pulse Check")
            score = st.slider("Zadovoljstvo (1-10):", 1, 10, 7)
            if st.button("Pošalji"): 
                conn.execute("INSERT INTO pulse_responses (score, timestamp, company_id) VALUES (?,?,?)", (score, datetime.now().strftime("%Y-%m-%d"), company_id))
                conn.commit(); st.success("Hvala!")

    # 5. 1-ON-1 (ISPRAVLJEN UPIT)
    with tabs[4]:
        st.subheader("📅 Sastanci")
        # Sada ovo odgovara novoj tablici meeting_notes
        notes = pd.read_sql_query("SELECT manager_id, date, notes, action_items FROM meeting_notes WHERE kadrovski_broj=? ORDER BY date DESC", conn, params=(username,))
        if not notes.empty: 
            for _, n in notes.iterrows():
                st.markdown(f"**{n['date']} (s {n['manager_id']})**")
                st.info(n['notes'])
                if n['action_items']: st.caption(f"Akcijski plan: {n['action_items']}")
        else: st.write("Nema zabilježenih sastanaka.")

    if not del_tasks.empty:
        with tabs[-1]:
            for _, task in del_tasks.iterrows():
                with st.expander(f"Zadatak: Procijeni {task['target_name']}"):
                    with st.form(f"task_eval_{task['id']}"):
                        tc1, tc2 = st.columns(2)
                        with tc1: tp = [render_metric_input(METRICS["p"][i], f"tp{i}", 3) for i in range(5)]
                        with tc2: tpot = [render_metric_input(METRICS["pot"][i], f"tpot{i}", 3, "pot") for i in range(5)]
                        if st.form_submit_button("Pošalji"):
                            ap, apot = sum(tp)/5, sum(tpot)/5
                            conn.execute("INSERT INTO evaluations (period, kadrovski_broj, manager_id, avg_performance, avg_potential, category, status, company_id) VALUES (?,?,?,?,?,?,?,?)", (current_period, task['target_id'], task['manager_id'], ap, apot, calculate_category(ap,apot), 'Submitted', company_id))
                            conn.execute("UPDATE delegated_tasks SET status='Completed' WHERE id=?", (task['id'],)); conn.commit(); st.success("Poslano!"); st.rerun()
    conn.close()