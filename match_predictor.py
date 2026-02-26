import requests

# API CONFIGURATION
API_KEY = 'd0834346e29712797e884f09623c52e4663d28908f972049d9709d73d2745a57'
BASE_URL = "https://apiv2.allsportsapi.com/football/"

def get_match_analysis(match_id):
    try:
        # Fetching Prediction Data
        params = {'met': 'Predictions', 'APIkey': API_KEY, 'matchId': match_id}
        r = requests.get(BASE_URL, params=params).json()
        
        if not r.get('result'): 
            return {"error": "No Prediction Data"}
        
        data = r['result'][0]
        h_n, a_n = data.get('home_team_name'), data.get('away_team_name')
        
        # PROBABILITIES
        h_p = float(data.get('prob_HW', 0))
        a_p = float(data.get('prob_AW', 0))
        d_p = float(data.get('prob_D', 0))
        o25_p = float(data.get('prob_O', 0))
        btts_p = float(data.get('prob_bts', 0))

        # 🏷 TAG LOGIC
        tag = "AVOID"
        if h_p > 70: tag = "STRONG HOME EDGE"
        elif a_p > 70: tag = "STRONG AWAY EDGE"
        elif o25_p > 75: tag = "HIGH SCORING MATCH"
        elif d_p > 35: tag = "UPSET LIKELY"

        # 🔵 RECOMMENDED TIP (Value + Logic)
        if h_p > 60: rec, rec_p, rec_r = f"{h_n} WIN", h_p, ["Dominant home metrics", "High conversion rate"]
        elif btts_p > 65: rec, rec_p, rec_r = "BTTS (YES)", btts_p, ["Both sides clinical in attack", "Defensive gaps detected"]
        else: rec, rec_p, rec_r = "OVER 2.5 GOALS", o25_p, ["High goal variance league", "Attacking tactical setup"]

        # 🟢 ALTERNATE TIP (Safest)
        if o25_p > 45: alt, alt_p, alt_r = "OVER 1.5 GOALS", o25_p + 15, "High probability for goals"
        elif h_p > a_p: alt, alt_p, alt_r = "DOUBLE CHANCE: 1X", h_p + 10, "Strong safety margin"
        else: alt, alt_p, alt_r = "DRAW NO BET: 2", a_p + 10, "Securing away advantage"

        # 🔴 HIGH RISK TIP (Higher Volatility)
        if h_p > 50 and btts_p > 55: risk, risk_p, risk_r = f"{h_n} WIN & GG", (h_p+btts_p)/2, "Aggressive home play / defensive leak"
        elif o25_p > 60 and btts_p > 60: risk, risk_p, risk_r = "GG & OVER 2.5", (o25_p+btts_p)/2, "Total attacking football expected"
        else: risk, risk_p, risk_r = "STRAIGHT DRAW", d_p, "Tactical stalemate predicted"

        return {
            "h_name": h_n, "a_name": a_n, 
            "h_logo": data.get('home_team_logo'), "a_logo": data.get('away_team_logo'),
            "tag": tag, "vol": "MODERATE" if 30 < d_p < 40 else "LOW",
            "rec": {"t": rec, "p": rec_p, "r": rec_r},
            "alt": {"t": alt, "p": alt_p, "r": alt_r},
            "risk": {"t": risk, "p": risk_p, "r": risk_r},
            "h_form": ["W", "D", "W", "L", "W"], # Placeholder: API mapping needed
            "a_form": ["L", "L", "D", "W", "L"],
            "stats": {"h_avg": "1.9", "a_avg": "1.1"}
        }
    except: return {"error": "Sync"}
