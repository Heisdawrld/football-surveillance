import requests

BSD_TOKEN = '043b3737804478238a3659401efaed0e36fbcf6d'
BASE_URL = "https://sports.bzzoiro.com/api"

def get_match_analysis(match_id):
    headers = {'Authorization': f'Token {BSD_TOKEN}'}
    try:
        p_res = requests.get(f"{BASE_URL}/predictions/{match_id}/", headers=headers).json()
        e = p_res.get('event', {})
        
        # PULLING REAL PROBABILITIES
        h_p = float(p_res.get('prob_home_win', 0))
        a_p = float(p_res.get('prob_away_win', 0))
        o25_p = float(p_res.get('prob_over_25', 0))
        btts_p = float(p_res.get('prob_btts', 0))

        # CALCULATE REAL FORM FROM API (Last 5 Games)
        # We extract the 'results' or 'form' strings directly from the API response
        h_form_raw = p_res.get('home_form', "DDDDD") # API fallback
        a_form_raw = p_res.get('away_form', "DDDDD")
        
        # Convert string "WDLWW" to list ['W', 'D', 'L', 'W', 'W']
        h_form = list(h_form_raw[-5:]) if h_form_raw else ["D"]*5
        a_form = list(a_form_raw[-5:]) if a_form_raw else ["D"]*5

        # INTENTIONAL MARKET ANALYSIS (No Correct Scores!)
        if h_p > 65: main_tip, tag = f"{e.get('home_team')} WIN", "HOME DOMINANCE"
        elif a_p > 65: main_tip, tag = f"{e.get('away_team')} WIN", "AWAY DOMINANCE"
        elif btts_p > 70: main_tip, tag = "BTTS (YES)", "GOAL EXCHANGE"
        elif o25_p > 70: main_tip, tag = "OVER 2.5 GOALS", "HIGH SCORING"
        elif h_p > 45 and o25_p > 50: main_tip, tag = "1X & OVER 1.5", "COMBO VALUE"
        else: main_tip, tag = "DRAW NO BET: 1" if h_p > a_p else "DRAW NO BET: 2", "SECURITY PLAY"

        # SAFEST (Low Risk)
        safer = "OVER 1.5" if o25_p > 50 else "DOUBLE CHANCE"

        # HIGH VALUE (Analyzed Risk)
        if h_p > 50 and btts_p > 60: risky = "HOME WIN & GG"
        elif o25_p > 75: risky = "OVER 3.5 GOALS"
        elif abs(h_p - a_p) < 5: risky = "STRAIGHT DRAW"
        else: risky = "WIN EITHER HALF"

        return {
            "h_name": e.get('home_team'), "a_name": e.get('away_team'),
            "tag": tag, "best_tip": {"t": main_tip, "p": max(h_p, a_p, o25_p, btts_p)},
            "safer": safer, "risky": risky,
            "h_form": h_form, "a_form": a_form,
            "intel": {"BTTS": f"{btts_p:.0f}%", "O/U 2.5": f"{o25_p:.0f}%", "1ST H. OVER 0.5": f"{(o25_p*0.7):.0f}%"}
        }
    except: return {"error": "sync"}
