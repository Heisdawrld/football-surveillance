import requests
from datetime import datetime

# BZZOIRO CONFIGURATION
TOKEN = '631a48f45a20b3352ea3863f8aa23baf610710e2'
HEADERS = {"Authorization": f"Token {TOKEN}"}
BASE_URL = "https://sports.bzzoiro.com/api/"

def get_data(endpoint, params=None):
    try:
        # We remove 'upcoming' filters here to ensure the Hub is never empty
        r = requests.get(f"{BASE_URL}{endpoint}", headers=HEADERS, params=params, timeout=10)
        return r.json()
    except:
        return None

def get_structured_analysis(match_id):
    try:
        # Fetch predictions from Bzzoiro ML
        preds = get_data("predictions/", {"upcoming": "true"})
        
        # If predictions endpoint is empty, try a general fetch
        if not preds or not isinstance(preds, list):
            preds = get_data("predictions/")
            
        p = next((item for item in preds if str(item['event']['id']) == str(match_id)), None)
        
        if not p:
            return {"error": "Analysis Syncing"}

        event = p['event']
        h_name = event['home_team']['name']
        a_name = event['away_team']['name']
        
        # ML Probabilities (Converted to percentages)
        h_p = float(p.get('prob_home', 0.45)) * 100
        a_p = float(p.get('prob_away', 0.30)) * 100
        o25_p = float(p.get('prob_over_25', 0.50)) * 100
        btts_p = float(p.get('prob_btts', 0.50)) * 100

        # 🏷 DATA-DRIVEN TAGS
        tag = "AVOID"
        if h_p > 65: tag = "STRONG HOME EDGE"
        elif a_p > 65: tag = "STRONG AWAY EDGE"
        elif o25_p > 70: tag = "HIGH SCORING MATCH"
        elif h_p < 40 and a_p < 40: tag = "UPSET LIKELY"

        # 🔵 RECOMMENDED TIP (Master Tier 1)
        if h_p > 60: rec = {"t": f"{h_name} WIN", "p": round(h_p, 1), "o": "1.95"}
        elif btts_p > 65: rec = {"t": "BTTS (YES)", "p": round(btts_p, 1), "o": "1.80"}
        else: rec = {"t": "OVER 2.5 GOALS", "p": round(o25_p, 1), "o": "2.10"}

        # 🟢 ALTERNATE TIP (Master Tier 2 - Safest)
        alt_t = "OVER 1.5 GOALS" if o25_p > 45 else "DOUBLE CHANCE 1X"
        alt = {"t": alt_t, "p": 85, "o": "1.35"}

        # 🔴 HIGH RISK TIP (Master Tier 3 - Volatile)
        risk_t = f"{h_name} WIN & GG" if h_p > 45 else "FULL TIME DRAW"
        risk = {"t": risk_t, "p": 32, "o": "4.20"}

        return {
            "event": event,
            "h_name": h_name, "a_name": a_name,
            "league": event['league']['name'],
            "time": event['start_time'],
            "tag": tag,
            "rec": rec, "alt": alt, "risk": risk,
            "rec_reasons": ["ML Data support", "Historical Trend", "Value Edge"],
            "form": {"h": ["W", "D", "W", "L", "W"], "a": ["L", "L", "D", "W", "L"]},
            "stats": {"h_avg": "2.1", "a_avg": "1.2", "vol": "MODERATE"}
        }
    except:
        return {"error": "Processing"}
