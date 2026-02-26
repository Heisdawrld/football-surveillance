import requests

BSD_TOKEN = '043b3737804478238a3659401efaed0e36fbcf6d'
BASE_URL = "https://sports.bzzoiro.com/api"

def get_match_analysis(match_id):
    headers = {'Authorization': f'Token {BSD_TOKEN}'}
    try:
        p_res = requests.get(f"{BASE_URL}/predictions/{match_id}/", headers=headers).json()
        e = p_res.get('event', {})
        h_p, a_p, d_p = float(p_res.get('prob_home_win', 0)), float(p_res.get('prob_away_win', 0)), float(p_res.get('prob_draw', 0))
        o25_p, btts_p = float(p_res.get('prob_over_25', 0)), float(p_res.get('prob_btts', 0))

        # 1. PRIMARY PREDICTION (Sensible Value Tip)
        if h_p > 60 and o25_p > 55: main_tip, tag = f"{e.get('home_team')} & Over 1.5", "HOME DOMINANCE"
        elif a_p > 60 and o25_p > 55: main_tip, tag = f"{e.get('away_team')} & Over 1.5", "AWAY DOMINANCE"
        elif btts_p > 65: main_tip, tag = "BTTS (YES)", "ATTACKING OVERLOAD"
        elif o25_p > 70: main_tip, tag = "OVER 2.5 GOALS", "HIGH SCORING MATCH"
        elif o25_p < 35: main_tip, tag = "UNDER 2.5 GOALS", "DEFENSIVE DEADLOCK"
        else: main_tip, tag = "DRAW NO BET: 1" if h_p > a_p else "DRAW NO BET: 2", "VALUE SECURED"

        # 2. SAFEST ALTERNATIVE (Low Risk)
        if o25_p > 45: safer = "OVER 1.5 GOALS"
        elif h_p > a_p: safer = "DOUBLE CHANCE: 1X"
        else: safer = "DOUBLE CHANCE: X2"

        # 3. HIGH RISK (Strategic Combo/Straight)
        if h_p > 50 and btts_p > 55: risky = f"{e.get('home_team')} WIN & GG"
        elif a_p > 50 and btts_p > 55: risky = f"{e.get('away_team')} WIN & GG"
        elif h_p > 55 and o25_p > 60: risky = f"{e.get('home_team')} WIN & OVER 2.5"
        elif a_p > 55 and o25_p > 60: risky = f"{e.get('away_team')} WIN & OVER 2.5"
        elif abs(h_p - a_p) < 5: risky = "FULL TIME DRAW"
        else: risky = "WIN EITHER HALF: HOME" if h_p > a_p else "WIN EITHER HALF: AWAY"

        return {
            "h_name": e.get('home_team'), "a_name": e.get('away_team'),
            "league": e.get('league_name'), "tag": tag,
            "best_tip": {"t": main_tip, "p": max(h_p, a_p, o25_p)},
            "safer": safer, "risky": risky,
            "form": ["W", "D", "W", "L", "W"], # Placeholder for Last 5
            "intel": {"BTTS": f"{btts_p:.0f}%", "O/U 2.5": f"{o25_p:.0f}%", "1ST H. OVER 0.5": f"{(o25_p*0.7):.0f}%"}
        }
    except: return {"error": "sync"}
