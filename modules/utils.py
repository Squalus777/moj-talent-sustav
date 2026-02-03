import hashlib
import pandas as pd
import json
import streamlit as st

SECRET_SALT = "SaaS_Secure_Performance_2026"

def make_hashes(password):
    return hashlib.sha256(str.encode(password + SECRET_SALT)).hexdigest()

def check_hashes(password, hashed_text):
    return make_hashes(password) == hashed_text

# Definiramo metriku - KLJUČ JE "title"
METRICS = {
    "p": [
        {"id": "P1", "title": "KPI i Ciljevi", "def": "Stupanj ostvarenja postavljenih kvantitativnih ciljeva.", "crit": "Za 5: Premašuje ciljeve za >20%."},
        {"id": "P2", "title": "Kvaliteta rada", "def": "Točnost, temeljitost i pouzdanost u izvršavanju zadataka.", "crit": "Za 5: Rad je bez grešaka, povjerenje je 100%."},
        {"id": "P3", "title": "Stručnost", "def": "Tehničko znanje i vještine potrebne za samostalan rad.", "crit": "Za 5: Ekspert u svom području, prenosi znanje drugima."},
        {"id": "P4", "title": "Odgovornost", "def": "Osjećaj vlasništva nad konačnim uspjehom zadatka ili projekta.", "crit": "Za 5: Ponaša se kao vlasnik, proaktivan je."},
        {"id": "P5", "title": "Suradnja", "def": "Dijeljenje informacija i timski rad.", "crit": "Za 5: Gradi mostove između odjela, pomaže kolegama."}
    ],
    "pot": [
        {"id": "POT1", "title": "Agilnost učenja", "def": "Brzina usvajanja novih znanja i prilagodba promjenama.", "crit": "Za 5: Uči izuzetno brzo, traži nove izazove."},
        {"id": "POT2", "title": "Autoritet / Utjecaj", "def": "Sposobnost utjecaja na druge bez formalne moći.", "crit": "Za 5: Prirodni lider, ljudi ga slušaju i poštuju."},
        {"id": "POT3", "title": "Šira slika", "def": "Razumijevanje kako vlastiti rad utječe na ciljeve tvrtke.", "crit": "Za 5: Razmišlja strateški, predlaže rješenja za cijelu firmu."},
        {"id": "POT4", "title": "Ambicija", "def": "Želja za napredovanjem i preuzimanjem veće odgovornosti.", "crit": "Za 5: Jasno pokazuje 'glad' za uspjehom i većom rolom."},
        {"id": "POT5", "title": "Stabilnost", "def": "Zadržavanje fokusa i smirenosti u stresnim situacijama.", "crit": "Za 5: Stijena u timu, fokusiran kad je najteže."}
    ]
}

def calculate_category(p, pot):
    # Osiguravamo da su p i pot brojevi (float), a ne Series
    try:
        p = float(p)
        pot = float(pot)
    except:
        return "N/A"
        
    if p>=4.5 and pot>=4.5: return "⭐️ Top Talent"
    elif p>=4 and pot>=3.5: return "🚀 High Performer"
    elif p>=3 and pot>=4: return "💎 Rastući potencijal"
    elif p>=3 and pot>=3: return "✅ Pouzdan suradnik"
    elif p<3 and pot>=3: return "🌱 Talent u razvoju"
    else: return "⚖️ Potrebno poboljšanje"

# Funkcija za vizualni prikaz kartica (Plavo/Narančasto)
def render_metric_input(m, key_prefix, val=3, type="perf"):
    # Određivanje boje i stila ovisno o tipu (Učinak vs Potencijal)
    bg_color = "#e6f3ff" if type == "perf" else "#fff0e6" # Svijetlo plava vs Svijetlo narančasta
    border_color = "#2196F3" if type == "perf" else "#FF9800" # Plava vs Narančasta
    
    # HTML za karticu
    st.markdown(f"""
    <div style="
        background-color: {bg_color}; 
        padding: 15px; 
        border-radius: 5px; 
        border-left: 5px solid {border_color}; 
        margin-bottom: 10px;">
        <div style="font-weight: bold; font-size: 16px;">{m['id']}: {m['title']}</div>
        <div style="font-size: 13px; color: #444; margin-top: 5px;">{m['def']}</div>
        <div style="font-size: 12px; color: #666; font-style: italic; margin-top: 5px;">{m['crit']}</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Sigurna konverzija vrijednosti u int za slider
    safe_val = 3
    try:
        safe_val = int(val)
    except:
        safe_val = 3
        
    return st.slider(f"Ocjena ({m['title']})", 1, 5, safe_val, key=f"{key_prefix}_{m['id']}")

def table_to_json_string(df):
    if df is None or df.empty: return "[]"
    return json.dumps(df.astype(str).to_dict(orient='records'), ensure_ascii=False)

def get_df_from_json(json_str, columns):
    try:
        data = json.loads(json_str) if json_str else []
        return pd.DataFrame(data, columns=columns)
    except: return pd.DataFrame(columns=columns)