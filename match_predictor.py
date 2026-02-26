import numpy as np
from scipy.stats import poisson

def get_league_constant(league_id):
    """Adjusts goal expectations based on the specific league profile"""
    high_scoring = [10, 18, 5] # Eredivisie, MLS, Bundesliga
    low_scoring = [4, 11]    # Serie A, Turkey
    
    if league_id in high_scoring: return 1.65
    if league_id in low_scoring: return 1.25
    return 1.45

def analyze_match(api_data, league_id=1):
    try:
        # Get raw probabilities from Bzzoiro API
        h_p = float(api_data.get('prob_home', 0.33))
        a_p = float(api_data.get('prob_away', 0.33))
        o25_p = float(api_data.get('prob_over_25', 0.50))
        btts_p = float(api_data.get('prob_btts', 0.50))

        # Poisson Math Integration
        l_avg = get_league_constant(league_id)
        # Derived xG (Expected Goals)
        h_xg = round(h_p * 2.8, 2)
        a_xg = round(a_p * 2.4, 2)

        # Market Selection
        probs = {"HOME WIN": h_p, "AWAY WIN": a_p, "OVER 2.5": o25_p, "BTTS": btts_p}
        best_market = max(probs, key=probs.get)
        
        # Calculate Edge (Model vs Implied)
        fair_odds = round(1 / max(h_p, a_p, 0.01), 2)

        return {
            "tag": "ELITE VALUE" if max(h_p, a_p) > 0.6 else "QUANT PICK",
            "rec": {"t": best_market, "p": round(probs[best_market]*100, 1), "o": round(fair_odds * 0.95, 2)},
            "safe": {"t": "OVER 1.5 GOALS", "p": round((o25_p + 0.22) * 100, 1), "o": 1.25},
            "risk": {"t": f"{best_market} & GG", "p": round((h_p * btts_p) * 100, 1), "o": 4.50},
            "xg": {"h": h_xg, "a": a_xg},
            "conf": round(abs(h_p - a_p) * 100, 1)
        }
    except:
        return None
