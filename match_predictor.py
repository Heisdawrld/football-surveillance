import requests

BSD_TOKEN = '043b3737804478238a3659401efaed0e36fbcf6d'
BASE_URL = "https://sports.bzzoiro.com/api"

def get_match_analysis(match_id):
    headers = {'Authorization': f'Token {BSD_TOKEN}'}
    try:
        # 1. Fetch Prediction Data
        p_res = requests.get(f"{BASE_URL}/predictions/{match_id}/", headers=headers).json()
        e = p_res.get('event', {})
        h_p, a_p = float(p_res.get('prob_home_win', 0)), float(p_res.get('prob_away_win', 0))
        o25_p, btts_p = float(p_res.get('prob_over_25', 0)), float(p_res.get('prob_btts', 0))

        # 2. Extract Real Form & Standings (if available in the response)
        # We look for the 'home_form' and 'away_form' strings like "WDLWW"
        h_f_raw = p_res.get('home_form', "")
        a_f_raw = p_res.get('away_form', "")
        
        # If the API returns empty, we show "N/A" instead of faking "D"
        h_form = list(h_f_raw[-5:]) if h_f_raw else ["?"]*5
        a_form = list(a_f_raw[-5:]) if a_f_raw else ["?"]*5

        # 3. Points and Standing Analysis
        # We pull these from the 'home_standing' and 'away_standing' objects
        h_s = p_res.get('home_standing', {})
        a_s = p_res.get('away_standing', {})
        
        stats = [
            {"label": "Rank", "h": h_s.get('rank', '-'), "a": a_s.get('rank', '-')},
            {"label": "Points", "h": h_s.get('points', '0'), "a": a_s.get('points', '0')},
            {"label": "Goal Diff", "h": h_s.get('goals_diff', '0'), "a": a_s.get('goals_diff', '0')}
        ]

        # 4. Market Logic (Intentional & Analyzed)
        if h_p > 68: main_tip, tag = f"{e.get('home_team')} WIN", "HOME DOMINANCE"
        elif a_p > 68: main_tip, tag = f"{e.get('away_team')} WIN", "AWAY DOMINANCE"
        elif btts_p > 72: main_tip, tag = "BTTS (YES)", "ATTACKING OVERLOAD"
        elif o25_p > 75: main_tip, tag = "OVER 2.5 GOALS", "HIGH SCORING"
        elif h_p > 48 and o25_p > 50: main_tip, tag = "1X & OVER 1.5", "VALUE COMBO"
        else: main_tip, tag = "DRAW NO BET: 1" if h_p > a_p else "DRAW NO BET: 2", "SECURITY PLAY"

        # Safest & Risky
        safer = "OVER 1.5 GOALS" if o25_p > 45 else "DOUBLE CHANCE"
        risky = "GG & OVER 2.5" if btts_p > 55 and o25_p > 60 else "WIN EITHER HALF"

        return {
            "h_name": e.get('home_team'), "a_name": e.get('away_team'),
            "tag": tag, "best_tip": {"t": main_tip, "p": max(h_p, a_p, o25_p, btts_p)},
            "safer": safer, "risky": risky,
            "h_form": h_form, "a_form": a_form, "stats": stats,
            "intel": {"BTTS": f"{btts_p:.0f}%", "O/U 2.5": f"{o25_p:.0f}%", "1ST H. OVER 0.5": f"{(o25_p*0.72):.0f}%"}
        }
    except: return {"error": "sync"}
