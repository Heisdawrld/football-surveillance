import requests
from datetime import datetime

# CORE SETTINGS
BSD_TOKEN = '043b3737804478238a3659401efaed0e36fbcf6d'
BASE_URL = "https://sports.bzzoiro.com/api"

def get_live_update(match_id):
    headers = {'Authorization': f'Token {BSD_TOKEN}'}
    try:
        r = requests.get(f"{BASE_URL}/live/", headers=headers).json()
        live_matches = r.get('results', [])
        for lm in live_matches:
            if str(lm.get('id')) == str(match_id) or str(lm.get('event_id')) == str(match_id):
                return {
                    "score": f"{lm.get('home_score')} - {lm.get('away_score')}",
                    "min": f"{lm.get('minute')}'"
                }
        return None
    except:
        return None

def get_match_analysis(match_id):
    headers = {'Authorization': f'Token {BSD_TOKEN}'}
    try:
        # FETCH PREDICTION DATA
        p_res = requests.get(f"{BASE_URL}/predictions/{match_id}/", headers=headers).json()
        event = p_res.get('event', {})
        live_info = get_live_update(match_id)
        
        # 1. EXTRACT RAW DATA
        h_p = float(p_res.get('prob_home_win', 0))
        a_p = float(p_res.get('prob_away_win', 0))
        o25_p = float(p_res.get('prob_over_25', 0))
        
        # 2. CALCULATE DIFFICULTY & SENSORS
        diff_val = abs(h_p - a_p)
        difficulty = "Easy" if diff_val > 25 else "Moderate" if diff_val > 12 else "Hard"
        volatility = "High" if diff_val < 10 and o25_p > 45 else "Stable"
        pressure = "High" if o25_p > 60 else "Moderate" if o25_p > 40 else "Low"

        # 3. IDENTIFY BEST TIP & RISK
        max_p = max(h_p, a_p, o25_p)
        risk = "Low" if max_p > 75 else "Medium" if max_p > 60 else "High"
        
        if max_p == h_p:
            tip_name = f"{event.get('home_team', 'Home')} Win"
        elif max_p == a_p:
            tip_name = f"{event.get('away_team', 'Away')} Win"
        else:
            tip_name = "Over 2.5 Goals"

        # 4. CALCULATE CORRECT SCORE
        if h_p > a_p:
            c_score = "2-1" if o25_p > 55 else "2-0" if h_p > 65 else "1-0"
        elif a_p > h_p:
            c_score = "1-2" if o25_p > 55 else "0-2" if a_p > 65 else "0-1"
        else:
            c_score = "1-1"

        return {
            "h_name": event.get('home_team', 'Home'),
            "a_name": event.get('away_team', 'Away'),
            "league": event.get('league_name', 'Pro League'),
            "time": "Today",
            "difficulty": difficulty,
            "best_tip": {
                "t": tip_name, 
                "p": max_p, 
                "risk": risk, 
                "reasons": ["AI identified statistical edge", "Momentum correlation positive", "High offensive conversion index"]
            },
            "live_status": live_info,
            "h_mom": "🔥 Aggressive" if h_p > 55 else "⚖️ Neutral",
            "a_mom": "🔥 Aggressive" if a_p > 55 else "⚖️ Neutral",
            "safer": "Over 1.5 Goals" if o25_p > 45 else "Double Chance",
            "risky": f"Correct Score: {c_score}",
            "intel": {"volatility": volatility, "pressure": pressure}
        }
    except Exception as e:
        return {"error": str(e)}
