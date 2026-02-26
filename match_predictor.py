import numpy as np
from scipy.stats import poisson

def get_poisson_probabilities(l_home, l_away):

    max_g = 10

    home_probs = poisson.pmf(range(max_g), l_home)
    away_probs = poisson.pmf(range(max_g), l_away)

    matrix = np.outer(home_probs, away_probs)

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

    league_avg = 1.45

    l_home = (home_avg_s / league_avg) * (away_avg_c / league_avg) * league_avg
    l_away = (away_avg_s / league_avg) * (home_avg_c / league_avg) * league_avg

    l_home += 0.15

    probs = get_poisson_probabilities(l_home, l_away)

    markets = {
        "HOME WIN": probs["home"],
        "DRAW": probs["draw"],
        "AWAY WIN": probs["away"],
        "OVER 2.5 GOALS": probs["over25"],
        "BTTS (YES)": probs["btts"]
    }

    sorted_markets = sorted(markets.items(), key=lambda x: x[1], reverse=True)
    rec_market, main_prob = sorted_markets[0]

    fair_odds = round(100 / main_prob, 2)

    sorted_1x2 = sorted(
        [probs["home"], probs["draw"], probs["away"]],
        reverse=True
    )
    confidence = round(sorted_1x2[0] - sorted_1x2[1], 2)

    return {
        "probs": {k: round(v, 1) for k, v in probs.items()},
        "recommendation": {
            "market": rec_market,
            "probability": round(main_prob, 1),
            "fair_odds": fair_odds
        },
        "confidence_gap": confidence,
        "xg": {
            "home": round(l_home, 2),
            "away": round(l_away, 2)
        }
    }
