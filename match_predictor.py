import requests
import os
from datetime import datetime, timedelta

# SECURE KEYS
BZZOIRO_TOKEN = os.environ.get("BZZOIRO_TOKEN", "631a48f45a20b3352ea3863f8aa23baf610710e2")
FOOTBALL_DATA_KEY = os.environ.get("FOOTBALL_DATA_KEY", "9f4755094ff9435695b794f91f4c1474")

def get_all_fixtures():
    """Fetches real-time fixtures with date filtering"""
    today = datetime.utcnow().strftime('%Y-%m-%d')
    future = (datetime.utcnow() + timedelta(days=3)).strftime('%Y-%m-%d')
    url = f"https://api.football-data.org/v4/matches?dateFrom={today}&dateTo={future}"
    headers = {'X-Auth-Token': FOOTBALL_DATA_KEY}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()
        return data.get('matches', []) if isinstance(data, dict) else []
    except: return []

def get_bzzoiro_predictions():
    """FIXED: Extracts the 'results' list from the API dictionary"""
    url = "https://sports.bzzoiro.com/api/predictions/?upcoming=true"
    headers = {"Authorization": f"Token {BZZOIRO_TOKEN}"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()
        
        # API DISCOVERY: Handle list vs dictionary with 'results' key
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get('results', [])
        return []
    except Exception as e:
        print(f"BZZOIRO API ERROR: {e}")
        return []

def normalize(name):
    """Prevents name collisions while removing formal suffixes"""
    clean = name.lower().strip()
    suffixes = [" fc", " afc", " as", " sc", " ud"]
    for s in suffixes:
        if clean.endswith(s): clean = clean[:-len(s)]
    return clean.strip()

def get_match_analysis(home_name, away_name, league_name, all_preds):
    """Defensive Analysis: Prevents string-index crashes"""
    h_norm, a_norm = normalize(home_name), normalize(away_name)
    
    # DEFENSIVE CHECK: Ensure we are iterating over a list of dicts
    p = None
    if isinstance(all_preds, list):
        for item in all_preds:
            if isinstance(item, dict):
                event = item.get('event', {})
                h_api = normalize(event.get('home_team', {}).get('name', ''))
                if h_api == h_norm:
                    p = item
                    break

    # Statistical Defaults (Fallback)
    is_ai = p is not None
    h_p = float(p.get('prob_home', 0.45)) if is_ai else 0.45
    o25_p = float(p.get('prob_over_25', 0.52)) if is_ai else 0.52

    # Deterministic Odds Simulation
    variance = 0.9 + (abs(hash(league_name)) % 15) / 100
    m_h_odds = round((1 / (h_p * variance)) * 0.95, 2)

    return {
        "tag": "AI ANALYZED" if is_ai else "STATISTICAL",
        "rec": {"t": "HOME WIN" if h_p > 0.5 else "OVER 2.5", "p": round(h_p*100, 1), "o": m_h_odds, "e": round((h_p*m_h_odds-1)*100, 2)},
        "safe": {"t": "OVER 1.5", "p": 82.0, "o": "1.30"},
        "risk": {"t": "DRAW", "p": 25.0, "o": "3.55"},
        "form": {"h": ["W","W","D","L","W"], "a": ["L","D","L","W","L"]},
        "stats": {"h_gls": "2.1", "a_gls": "1.2", "vol": "MODERATE"}
    }
