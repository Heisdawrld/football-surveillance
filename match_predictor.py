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

        # 1. RECOMMENDED TIP (Most Possible with Good Odds)
        if h_p > 65: main_tip, tag = f"{e.get('home_team')} WIN", "HOME DOMINANCE"
        elif a_p > 65: main_tip, tag = f"{e.get('away_team')} WIN", "AWAY DOMINANCE"
        elif btts_p > 65: main_tip, tag = "BTTS (YES)", "ATTACKING OVERLOAD"
        elif o25_p > 70: main_tip, tag = "OVER 2.5 GOALS", "HIGH SCORING"
        elif h_p > 45 and o25_p > 50: main_tip, tag = "1X & OVER 1.5", "COMBO VALUE"
        else: main_tip, tag = "DRAW NO BET: 1" if h_p > a_p else "DRAW NO BET: 2", "SECURITY PLAY"

        # 2. SAFEST ALTERNATIVE (The "Shield" Tip)
        if o25_p > 50: safer = "OVER 1.5 GOALS"
        elif h_p > a_p: safer = "DOUBLE CHANCE: 1X"
        else: safer = "DOUBLE CHANCE: X2"

        # 3. HIGH RISK (Intentional Value)
        if h_p > 50 and btts_p > 55: risky = "HOME WIN & GG"
        elif h_p > 55 and o25_p > 60: risky = "HOME & OVER 2.5"
        elif abs(h_p - a_p) < 7: risky = "STRAIGHT DRAW"
        else: risky = "WIN EITHER HALF: HOME" if h_p > a_p else "WIN EITHER HALF: AWAY"

        return {
            "h_name": e.get('home_team'), "a_name": e.get('away_team'),
            "league": e.get('league_name'), "tag": tag,
            "best_tip": {"t": main_tip, "p": max(h_p, a_p, btts_p, o25_p)},
            "safer": safer, "risky": risky,
            "h_form": ["W", "D", "W", "L", "W"], # Placeholder for now
            "a_form": ["L", "L", "W", "D", "L"],
            "intel": {"BTTS": f"{btts_p:.0f}%", "O/U 2.5": f"{o25_p:.0f}%", "1ST H. OVER 0.5": f"{(o25_p*0.75):.0f}%"}
        }
    except: return {"error": "sync"}
