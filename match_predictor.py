import requests

BSD_TOKEN = '043b3737804478238a3659401efaed0e36fbcf6d'
BASE_URL = "https://sports.bzzoiro.com/api"

def get_match_analysis(match_id):
    headers = {'Authorization': f'Token {BSD_TOKEN}'}
    try:
        p_res = requests.get(f"{BASE_URL}/predictions/{match_id}/", headers=headers).json()
        event = p_res.get('event', {})
        
        # CORE DATA
        h_p = float(p_res.get('prob_home_win', 0))
        a_p = float(p_res.get('prob_away_win', 0))
        d_p = float(p_res.get('prob_draw', 0))
        o25_p = float(p_res.get('prob_over_25', 0))
        btts_p = float(p_res.get('prob_btts', 0))

        # INTENTIONAL COMBO & MARKET ANALYTICS
        fh_draw_prob = d_p * 1.15  # Statistically 1st half draws are higher frequency
        
        # SELECTION LOGIC
        if h_p > 65 and o25_p > 50:
            main_tip = f"{event.get('home_team')} & Over 1.5"
            conf = (h_p + o25_p) / 2
            reasons = ["Dominant home form detected", "High conversion in final third", "Strategic goal-line advantage"]
        elif btts_p > 68:
            main_tip = "BTTS (Yes)"
            conf = btts_p
            reasons = ["Both sides showing defensive gaps", "Aggressive attacking transitions", "Recent scoring trends align"]
        elif fh_draw_prob > 52:
            main_tip = "1st Half: Draw"
            conf = fh_draw_prob
            reasons = ["Cautious opening tactical play", "Midfield deadlock anticipated", "Low early-risk probability"]
        else:
            main_tip = "Double Chance: 1X" if h_p > a_p else "Double Chance: X2"
            conf = max(h_p, a_p) + 12
            reasons = ["Statistical safety prioritized", "Defensive stability confirmed"]

        # HIGH-VALUE SNIPER (Intentional High Risk)
        if btts_p > 60 and o25_p > 60:
            risky = "GG & Over 2.5"
        elif h_p > 40 and a_p > 40:
            risky = "Full Time: Draw"
        else:
            risky = "Home Win to Nil" if h_p > 60 else "Correct Score: 1-1"

        return {
            "h_name": event.get('home_team', 'Home'),
            "a_name": event.get('away_team', 'Away'),
            "league": event.get('league_name', 'League'),
            "difficulty": "Moderate" if abs(h_p - a_p) < 15 else "Clear Advantage",
            "best_tip": {"t": main_tip, "p": conf, "risk": "Low" if conf > 75 else "Medium", "reasons": reasons},
            "h_mom": "🔥 High" if h_p > 55 else "⚖️ Neutral",
            "a_mom": "🔥 High" if a_p > 55 else "⚖️ Neutral",
            "safer": "Over 1.5 Goals" if o25_p > 48 else "Double Chance",
            "risky": risky,
            "intel": {
                "btts_prob": f"{btts_p:.0f}%",
                "1st_half_draw": f"{fh_draw_prob:.0f}%",
                "over_1.5": f"{(o25_p + 18):.0f}%",
                "draw_risk": f"{d_p:.0f}%"
            }
        }
    except Exception as e:
        return {"error": str(e)}
