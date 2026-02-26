import numpy as np
from scipy.stats import poisson

def get_poisson_probabilities(l_home, l_away):
    """Calculates full match matrix for 1X2, Goals, and BTTS"""
    max_g = 10
    home_probs = poisson.pmf(range(max_g), l_home)
    away_probs = poisson.pmf(range(max_g), l_away)
    
    # Create the score matrix
    matrix = np.outer(home_probs, away_probs)
    
    # Outcomes math
    home_win = np.sum(np.tril(matrix, -1))
    draw = np.sum(np.diag(matrix))
    away_win = np.sum(np.triu(matrix, 1))
    
    goal_sum = np.add.outer(range(max_g), range(max_g))
    over25 = np.sum(matrix[goal_sum >= 3])
    over15 = np.sum(matrix[goal_sum >= 2])
    btts = np.sum(matrix[1:, 1:])

    return {
        "home": home_win * 100,
        "draw": draw * 100,
        "away": away_win * 100,
        "over25": over25 * 100,
        "over15": over15 * 100,
        "btts": btts * 100
    }

def analyze_match(home_avg_s, away_avg_s, home_avg_c, away_avg_c):
    """The Engine: Returns Master Prompt compliant analysis"""
    league_avg = 1.45
    l_home = (home_avg_s / league_avg) * (away_avg_c / league_avg) * league_avg
    l_away = (away_avg_s / league_avg) * (home_avg_c / league_avg) * league_avg
    
    # Manual adjustment for Home Advantage
    l_home += 0.15

    probs = get_poisson_probabilities(l_home, l_away)

    # Market Selection Logic
    markets = {
        "HOME WIN": probs["home"],
        "DRAW": probs["draw"],
        "AWAY WIN": probs["away"],
        "OVER 2.5 GOALS": probs["over25"],
        "BTTS (YES)": probs["btts"]
    }

    sorted_m = sorted(markets.items(), key=lambda x: x[1], reverse=True)
    rec_market, main_prob = sorted_m[0]

    # Confidence Gap Math (1X2 Spread)
    sorted_1x2 = sorted([probs["home"], probs["draw"], probs["away"]], reverse=True)
    confidence = round(sorted_1x2[0] - sorted_1x2[1], 2)

    return {
        "tag": "STRONG EDGE" if confidence > 25 else "VALUE PLAY",
        "probs": {k: round(v, 1) for k, v in probs.items()},
        "rec": {
            "t": rec_market,
            "p": round(main_prob, 1),
            "o": round(100 / (main_prob * 0.95), 2) # Adding 5% bookie margin to fair odds
        },
        "safe": {
            "t": "OVER 1.5 GOALS" if probs["over15"] > 70 else "DOUBLE CHANCE",
            "p": round(probs["over15"], 1),
            "o": 1.28
        },
        "risk": {
            "t": f"{rec_market} & BTTS",
            "p": round((main_prob/100 * probs["btts"]/100) * 100, 1),
            "o": 4.10
        },
        "xg": {"h": round(l_home, 2), "a": round(l_away, 2)},
        "conf": confidence
    }
