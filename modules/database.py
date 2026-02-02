import sqlite3
import os
import shutil
import glob
from datetime import datetime

DB_FILE = 'talent_database.db'

def get_connection():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    
    # 1. TABLICE JEZGRE
    c.execute('CREATE TABLE IF NOT EXISTS companies (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, subdomain TEXT, logo_url TEXT, plan_type TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, role TEXT, department TEXT, company_id INTEGER)')
    c.execute('CREATE TABLE IF NOT EXISTS employees_master (kadrovski_broj TEXT PRIMARY KEY, ime_prezime TEXT, radno_mjesto TEXT, department TEXT, manager_id TEXT, company_id INTEGER, is_manager INTEGER DEFAULT 0, active INTEGER DEFAULT 1)')
    c.execute('CREATE TABLE IF NOT EXISTS evaluations (id INTEGER PRIMARY KEY AUTOINCREMENT, period TEXT, kadrovski_broj TEXT, ime_prezime TEXT, radno_mjesto TEXT, department TEXT, manager_id TEXT, p1 REAL, p2 REAL, p3 REAL, p4 REAL, p5 REAL, pot1 REAL, pot2 REAL, pot3 REAL, pot4 REAL, pot5 REAL, avg_performance REAL, avg_potential REAL, category TEXT, action_plan TEXT, status TEXT, feedback_date TEXT, company_id INTEGER, is_self_eval INTEGER DEFAULT 0)')
    c.execute('CREATE TABLE IF NOT EXISTS app_settings (setting_key TEXT PRIMARY KEY, setting_value TEXT, company_id INTEGER)')
    c.execute('CREATE TABLE IF NOT EXISTS periods (period_name TEXT PRIMARY KEY, deadline TEXT, company_id INTEGER)')
    c.execute('CREATE TABLE IF NOT EXISTS audit_log (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, user TEXT, action TEXT, details TEXT, company_id INTEGER)')
    
    # 2. TABLICE ZA CILJEVE I DETALJNE KPI (Rješenje za vašu grešku)
    c.execute('''CREATE TABLE IF NOT EXISTS goals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    period TEXT, 
                    kadrovski_broj TEXT, 
                    manager_id TEXT, 
                    title TEXT, 
                    description TEXT, 
                    weight REAL, 
                    progress REAL, 
                    status TEXT, 
                    last_updated TEXT, 
                    deadline TEXT, 
                    company_id INTEGER)''')

    c.execute('''CREATE TABLE IF NOT EXISTS goal_kpis (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    goal_id INTEGER, 
                    description TEXT, 
                    weight REAL, 
                    progress REAL, 
                    deadline TEXT, 
                    FOREIGN KEY (goal_id) REFERENCES goals (id))''')
    
    # 3. INDIVIDUALNI RAZVOJNI PLANOVI (IDP)
    c.execute('''CREATE TABLE IF NOT EXISTS development_plans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    period TEXT, 
                    kadrovski_broj TEXT, 
                    manager_id TEXT, 
                    strengths TEXT, 
                    areas_improve TEXT, 
                    career_goal TEXT, 
                    json_70 TEXT, 
                    json_20 TEXT, 
                    json_10 TEXT, 
                    support_needed TEXT, 
                    support_notes TEXT, 
                    status TEXT, 
                    company_id INTEGER)''')

    # 4. SASTANCI I KOMERCIJALNI MODULI
    c.execute('CREATE TABLE IF NOT EXISTS meeting_notes (kadrovski_broj TEXT, manager_id TEXT, date TEXT, notes TEXT, company_id INTEGER)')
    c.execute('CREATE TABLE IF NOT EXISTS pulse_responses (id INTEGER PRIMARY KEY AUTOINCREMENT, survey_id INTEGER, score INTEGER, comment TEXT, timestamp TEXT, company_id INTEGER)')
    c.execute('CREATE TABLE IF NOT EXISTS recognitions (id INTEGER PRIMARY KEY AUTOINCREMENT, sender_id TEXT, receiver_id TEXT, message TEXT, category TEXT, timestamp TEXT, company_id INTEGER)')

    # Automatska migracija stupaca
    try: c.execute("ALTER TABLE pulse_responses ADD COLUMN timestamp TEXT")
    except: pass

    # Inicijalne postavke
    if c.execute("SELECT COUNT(*) FROM app_settings").fetchone()[0] == 0:
        c.execute("INSERT INTO app_settings (setting_key, setting_value, company_id) VALUES ('active_period', '2026-Q1', 1)")
        c.execute("INSERT INTO periods (period_name, deadline, company_id) VALUES ('2026-Q1', '2026-03-31', 1)")
    
    conn.commit()
    conn.close()

def log_action(user, action, details, company_id=1):
    conn = get_connection()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("INSERT INTO audit_log (timestamp, user, action, details, company_id) VALUES (?,?,?,?,?)", (ts, user, action, details, company_id))
    conn.commit()
    conn.close()

def get_active_period_info():
    conn = get_connection()
    res = conn.execute("SELECT setting_value FROM app_settings WHERE setting_key='active_period'").fetchone()
    if res:
        period = res[0]
        dl = conn.execute("SELECT deadline FROM periods WHERE period_name=?", (period,)).fetchone()
        conn.close()
        return period, dl[0] if dl else "Nema roka"
    conn.close()
    return "2026-Q1", ""

def perform_backup(auto=False):
    if not os.path.exists("backups"): os.makedirs("backups")
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    fn = f"backups/backup_{'AUTO' if auto else 'MANUAL'}_{ts}.db"
    shutil.copy2(DB_FILE, fn)
    return True, fn

def get_available_backups():
    return glob.glob("backups/*.db")