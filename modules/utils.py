import hashlib
import pandas as pd
import json
import streamlit as st

# Komercijalni Sigurnosni Ključ (Salt)
SECRET_SALT = "SaaS_Secure_Performance_2026"

def make_hashes(password):
    return hashlib.sha256(str.encode(password + SECRET_SALT)).hexdigest()

def check_hashes(password, hashed_text):
    return make_hashes(password) == hashed_text

METRICS = {
    "p": [
        {"id": "P1", "title": "KPI i Ciljevi", "def": "Ispunjenje ciljeva.", "crit": "Za 5: Premašuje očekivanja."},
        {"id": "P2", "title": "Kvaliteta rada", "def": "Točnost i pouzdanost.", "crit": "Za 5: Bez grešaka."},
        {"id": "P3", "title": "Stručnost", "def": "Tehničko znanje.", "crit": "Za 5: Ekspert."},
        {"id": "P4", "title": "Odgovornost", "def": "Vlasništvo nad zadatkom.", "crit": "Za 5: Proaktivan."},
        {"id": "P5", "title": "Suradnja", "def": "Timski rad.", "crit": "Za 5: Gradi mostove."}
    ],
    "pot": [
        {"id": "POT1", "title": "Agilnost učenja", "def": "Usvajanje novih vještina.", "crit": "Za 5: Iznimno brzo."},
        {"id": "POT2", "title": "Autoritet", "def": "Utjecaj na okolinu.", "crit": "Za 5: Lider bez titule."},
        {"id": "POT3", "title": "Šira slika", "def": "Strategic Mindset.", "crit": "Za 5: Razumije biznis."},
        {"id": "POT4", "title": "Ambicija", "def": "Želja za rastom.", "crit": "Za 5: 'Gladan' uspjeha."},
        {"id": "POT5", "title": "Stabilnost", "def": "Upravljanje stresom.", "crit": "Za 5: Fokusiran kad je najteže."}
    ]
}

def calculate_category(p, pot):
    if p>=4 and pot>=4: return "⭐️ Top Talent"
    elif p>=4 and pot>=3: return "🚀 High Performer"
    elif p>=3 and pot>=4: return "💎 Rastući potencijal"
    elif p>=3 and pot>=3: return "✅ Pouzdan suradnik"
    elif p<3 and pot>=4: return "🌱 Talent u razvoju"
    else: return "⚖️ Solid Performer"

def render_metric_input(m, key_prefix, val=3, type="perf"):
    css_class = "metric-card-perf" if type == "perf" else "metric-card-pot"
    st.markdown(f'<div class="{css_class}"><b>{m["id"]}: {m["title"]}</b><br><small>{m["def"]}</small></div>', unsafe_allow_html=True)
    return st.slider(f"Ocjena ({m['id']})", 1, 5, int(val), key=f"{key_prefix}_{m['id']}")

def table_to_json_string(df):
    if df is None or df.empty: return "[]"
    return json.dumps(df.astype(str).to_dict(orient='records'), ensure_ascii=False)

def get_df_from_json(json_str, columns):
    try:
        data = json.loads(json_str) if json_str else []
        return pd.DataFrame(data, columns=columns)
    except: return pd.DataFrame(columns=columns)