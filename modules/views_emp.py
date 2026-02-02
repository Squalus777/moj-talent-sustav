import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import sqlite3
from modules.database import get_connection, get_active_period_info, DB_FILE
from modules.utils import METRICS, calculate_category, render_metric_input

def render_employee_view():
    conn = get_connection()
    username = st.session_state['username']
    company_id = st.session_state['company_id']
    current_period, _ = get_active_period_info()

    st.header(f"👋 Dobrodošli, {username}")
    tabs = st.tabs(["📈 Napredak", "🎯 Ciljevi", "📝 Samoprocjena", "🙌 Pohvale & Pulse", "🤝 Moji 1-on-1"])

    # --- TAB: POHVALE & PULSE ---
    with tabs[3]:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("📮 Pošalji pohvalu kolegi")
            with st.form("kudos_form"):
                receiver = st.selectbox("Kolega:", pd.read_sql_query("SELECT username FROM users WHERE company_id=? AND username!=?", conn, params=(company_id, username))['username'])
                msg = st.text_area("Poruka zahvale:")
                cat = st.selectbox("Kategorija:", ["Timski rad", "Inovativnost", "Pomoć u nevolji", "Stručnost"])
                if st.form_submit_button("Pošalji"):
                    conn.execute("INSERT INTO recognitions (sender_id, receiver_id, message, category, timestamp, company_id) VALUES (?,?,?,?,?,?)",
                                 (username, receiver, msg, cat, datetime.now().strftime("%Y-%m-%d"), company_id))
                    conn.commit(); st.success("Pohvala poslana!")

        with c2:
            st.subheader("📊 Pulse Anketa")
            active_survey = pd.read_sql_query("SELECT * FROM pulse_surveys WHERE active=1 AND company_id=? LIMIT 1", conn, params=(company_id,))
            if not active_survey.empty:
                st.info(active_survey.iloc[0]['question'])
                score = st.select_slider("Vaše zadovoljstvo (1-10):", options=range(1,11), value=7)
                comment = st.text_input("Dodatni komentar (opcionalno):")
                if st.button("Pošalji anonimno"):
                    conn.execute("INSERT INTO pulse_responses (survey_id, score, comment, company_id) VALUES (?,?,?,?)",
                                 (int(active_survey.iloc[0]['id']), score, comment, company_id))
                    conn.commit(); st.success("Hvala na povratnoj informaciji!")
            else: st.write("Trenutno nema aktivnih anketa.")

    # --- TAB: 1-on-1 ---
    with tabs[4]:
        st.subheader("📝 Bilješke s prošlih sastanaka")
        meetings = pd.read_sql_query("SELECT meeting_date, notes, action_items FROM meetings_1on1 WHERE employee_id=? AND company_id=? ORDER BY meeting_date DESC", conn, params=(username, company_id))
        if not meetings.empty: st.table(meetings)
        else: st.info("Još niste imali zabilježenih sastanaka.")

    # (Ostali tabovi ostaju prema tvojoj trenutnoj verziji...)
    conn.close()