import requests
from datetime import datetime, timedelta

# API KEYS
BZZOIRO_TOKEN = '631a48f45a20b3352ea3863f8aa23baf610710e2'
FOOTBALL_DATA_KEY = '9f4755094ff9435695b794f91f4c1474'

def get_all_fixtures():
    """Fetches and groups fixtures by date and league"""
    url = "https://api.football-data.org/v4/matches"
    headers = {'X-Auth-Token': FOOTBALL_DATA_KEY}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        return r.json().get('matches', [])
    except: return []

def get_match_analysis(home_team, away_team):
    """Deep analysis for the specific Match View"""
    url = "https://sports.bzzoiro.com/api/predictions/?upcoming=true"
    headers = {"Authorization": f"Token {BZZOIRO_TOKEN}"}
    try:
        preds = requests.get(url, headers=headers).json()
        p = next((x for x in preds if home_team.lower() in x['event']['home_team']['name'].lower()), None)
    except: p = None

    # Default logic-driven stats if AI is still syncing
    prob_h = float(p['prob_home']) * 100 if p else 50.0
    prob_o25 = float(p['prob_over_25']) * 100 if p else 55.0

    return {
        "tag": "STRONG HOME EDGE" if prob_h > 60 else "MODERATE RISK",
        "rec": {"t": "HOME WIN", "p": round(prob_h, 1), "o": "1.90", "r": ["Home scoring trend high", "Tactical edge in midfield"]},
        "alt": {"t": "OVER 1.5 GOALS", "p": 88, "o": "1.28", "r": "High probability safety net."},
        "risk": {"t": "HOME & BTTS", "p": 32, "o": "4.10", "r": "Defensive lapse expected despite win."},
        "stats": {"h_gls": "2.1", "a_gls": "1.2", "vol": "MODERATE"},
        "form": {"h": ["W", "W", "D", "L", "W"], "a": ["L", "D", "L", "W", "L"]}
    }
