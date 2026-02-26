"""
match_predictor.py — ProPredictor Engine v2
Uses real API fields: expected_home_goals, expected_away_goals,
prob_home_win, prob_draw, prob_away_win, prob_over_15/25/35, prob_btts_yes
Adds: momentum score, upset index, value edge vs bookmaker odds
"""

import math

def poisson_pmf(k, lam):
    """P(X = k) for Poisson distribution."""
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return (lam ** k) * math.exp(-lam) / math.factorial(k)

def calculate_likely_score(h_xg, a_xg, over_15_prob=50, max_goals=6):
    """
    Calculate most likely score from xG using Poisson.
    When Over 1.5 is highly probable but 0-0 is peak Poisson prob,
    return the most likely SCORING scoreline instead — avoids contradiction.
    """
    scores = []
    for h in range(max_goals + 1):
        for a in range(max_goals + 1):
            p = poisson_pmf(h, h_xg) * poisson_pmf(a, a_xg)
            scores.append((p, h, a))
    scores.sort(reverse=True)
    best_p, best_h, best_a = scores[0]
    # If 0-0 leads but Over 1.5 says goals are very likely, show best scoring line
    if best_h == 0 and best_a == 0 and over_15_prob >= 65:
        for p, h, a in scores:
            if h + a >= 1:
                return f"{h}-{a}"
    return f"{best_h}-{best_a}"

FORM_WEIGHTS = [1.0, 1.2, 1.4, 1.6, 1.8]
FORM_VALUE   = {"W": 1.0, "D": 0.4, "L": 0.0}

def form_score(form_list):
    if not form_list:
        return 0.5
    results = [r.upper() for r in list(form_list)[-5:]]
    weights = FORM_WEIGHTS[-len(results):]
    score   = sum(FORM_VALUE.get(r, 0.5) * w for r, w in zip(results, weights))
    return round(score / sum(weights), 4)

def form_trend(form_list):
    if not form_list or len(form_list) < 3:
        return "STABLE"
    results = [r.upper() for r in list(form_list)[-5:]]
    vals    = [FORM_VALUE.get(r, 0.5) for r in results]
    recent  = sum(vals[-2:]) / 2
    earlier = sum(vals[:2])  / 2
    diff    = recent - earlier
    if diff >  0.25: return "RISING"
    if diff < -0.25: return "FALLING"
    return "STABLE"

def momentum_score(h_form, a_form, h_xg, a_xg):
    h_f = form_score(h_form)
    a_f = form_score(a_form)
    total_xg   = max(h_xg + a_xg, 0.1)
    h_xg_share = h_xg / total_xg
    a_xg_share = a_xg / total_xg
    h_momentum = round((h_f * 0.6 + h_xg_share * 0.4) * 100, 1)
    a_momentum = round((a_f * 0.6 + a_xg_share * 0.4) * 100, 1)
    h_trend    = form_trend(h_form)
    a_trend    = form_trend(a_form)
    gap = abs(h_momentum - a_momentum)
    if gap < 8:
        narrative = "Evenly matched — coin flip momentum"
    elif h_momentum > a_momentum:
        narrative = f"Home carrying stronger momentum ({h_trend.lower()})"
    else:
        narrative = f"Away side in better form ({a_trend.lower()})"
    return {"home": h_momentum, "away": a_momentum,
            "h_trend": h_trend, "a_trend": a_trend, "narrative": narrative}

def upset_index(h_win, a_win, h_form, a_form, h_standing, a_standing):
    if h_win >= a_win:
        fav_prob  = h_win / 100
        dog_form  = form_score(a_form)
        fav_stand = h_standing or 10
        dog_stand = a_standing or 10
    else:
        fav_prob  = a_win / 100
        dog_form  = form_score(h_form)
        fav_stand = a_standing or 10
        dog_stand = h_standing or 10
    dog_prob     = 1 - fav_prob
    prob_gap     = fav_prob - dog_prob
    stand_diff   = abs((fav_stand or 10) - (dog_stand or 10))
    stand_factor = min(stand_diff / 10, 1.0)
    raw   = (dog_form * 0.4 + stand_factor * 0.3 + (1 - prob_gap) * 0.3)
    index = round(raw * 100, 1)
    if index >= 65 and prob_gap > 0.15:
        return {"index": index, "label": "HIGH UPSET RISK",      "color": "warn"}
    elif index >= 50:
        return {"index": index, "label": "MODERATE UPSET RISK",  "color": "blue"}
    else:
        return {"index": index, "label": "LOW UPSET RISK",        "color": "muted"}

def value_edge(market_prob, bookmaker_odds):
    if not bookmaker_odds or bookmaker_odds <= 1.0:
        return None
    implied = 1 / bookmaker_odds
    edge    = (market_prob / 100) - implied
    return round(edge * 100, 1)

def style_profile(h_xg, a_xg, o25, btts):
    total = h_xg + a_xg
    if total >= 3.0:   style = "HIGH SCORING — both teams creating plenty"
    elif total >= 2.2: style = "OPEN GAME — goals likely from both sides"
    elif total >= 1.5: style = "BALANCED — compact, contested midfield battle"
    else:              style = "LOW SCORING — defensive, set-pieces could decide it"
    if btts >= 65:     style += " · Both teams likely to score"
    elif btts <= 35:   style += " · Clean sheet possible"
    return style

def select_best_market(h_win, draw, a_win, o15, o25, o35, btts):
    candidates = {
        "HOME WIN":  h_win,
        "DRAW":      draw  * 0.85,
        "AWAY WIN":  a_win,
        "OVER 1.5":  o15,
        "OVER 2.5":  o25,
        "OVER 3.5":  o35   * 0.85,
        "BTTS":      btts,
    }
    best = max(candidates, key=candidates.get)
    actuals = {"HOME WIN": h_win, "DRAW": draw, "AWAY WIN": a_win,
               "OVER 1.5": o15, "OVER 2.5": o25, "OVER 3.5": o35, "BTTS": btts}
    return best, round(actuals[best], 1)

def analyze_match(api_data, league_id=None):
    try:
        event  = api_data.get("event", {})
        league = event.get("league", {})
        l_id   = league_id or league.get("id", 1)

        h_win  = float(api_data.get("prob_home_win",  33.3))
        draw   = float(api_data.get("prob_draw",      33.3))
        a_win  = float(api_data.get("prob_away_win",  33.3))
        o15    = float(api_data.get("prob_over_15",   70.0))
        o25    = float(api_data.get("prob_over_25",   50.0))
        o35    = float(api_data.get("prob_over_35",   25.0))
        btts   = float(api_data.get("prob_btts_yes",  50.0))
        h_xg   = float(api_data.get("expected_home_goals", 1.2))
        a_xg   = float(api_data.get("expected_away_goals", 1.0))
        conf   = float(api_data.get("confidence",     40.0))
        # Calculate most likely score from xG — ignore API's field (often wrong)
        likely = calculate_likely_score(h_xg, a_xg, o15)

        odds_h    = event.get("odds_home")
        odds_d    = event.get("odds_draw")
        odds_a    = event.get("odds_away")
        odds_o15  = event.get("odds_over_15")
        odds_o25  = event.get("odds_over_25")
        odds_btts = event.get("odds_btts_yes")

        h_form  = api_data.get("home_form", [])
        a_form  = api_data.get("away_form", [])
        h_stand = api_data.get("home_standing")
        a_stand = api_data.get("away_standing")

        best_mkt, best_prob = select_best_market(h_win, draw, a_win, o15, o25, o35, btts)
        fair_odds = round(100 / max(best_prob, 1), 2)

        edge_map = {
            "HOME WIN":  value_edge(h_win, odds_h),
            "DRAW":      value_edge(draw,  odds_d),
            "AWAY WIN":  value_edge(a_win, odds_a),
            "OVER 1.5":  value_edge(o15,   odds_o15),
            "OVER 2.5":  value_edge(o25,   odds_o25),
            "BTTS":      value_edge(btts,  odds_btts),
        }
        best_edge = edge_map.get(best_mkt)

        if best_prob >= 68:   tag = "ELITE VALUE"
        elif best_prob >= 58: tag = "STRONG PICK"
        elif best_prob >= 50: tag = "QUANT EDGE"
        else:                 tag = "MONITOR"

        momentum = momentum_score(h_form, a_form, h_xg, a_xg)
        upset    = upset_index(h_win, a_win, h_form, a_form, h_stand, a_stand)
        style    = style_profile(h_xg, a_xg, o25, btts)

        all_mkts    = {"HOME WIN": h_win, "DRAW": draw, "AWAY WIN": a_win,
                       "OVER 1.5": o15, "OVER 2.5": o25, "BTTS": btts}
        sorted_mkts = sorted(all_mkts.items(), key=lambda x: x[1], reverse=True)
        second      = next((m for m in sorted_mkts if m[0] != best_mkt), sorted_mkts[-1])

        return {
            "tag":          tag,
            "xg_h":         round(h_xg, 2),
            "xg_a":         round(a_xg, 2),
            "likely_score": likely,
            "1x2":          {"home": round(h_win,1), "draw": round(draw,1), "away": round(a_win,1)},
            "markets":      {"over_15": round(o15,1), "over_25": round(o25,1),
                             "over_35": round(o35,1), "under_25": round(100-o25,1), "btts": round(btts,1)},
            "rec":          {"t": best_mkt, "p": round(best_prob,1), "odds": fair_odds, "edge": best_edge},
            "second":       {"t": second[0], "p": round(second[1],1)},
            "confidence":   round(conf, 1),
            "momentum":     momentum,
            "upset":        upset,
            "style":        style,
            "form":         {"home": list(h_form)[-5:], "away": list(a_form)[-5:]},
            "standings":    {"home": h_stand, "away": a_stand},
        }

    except Exception as e:
        import traceback
        print(f"[Predictor Error] {e}\n{traceback.format_exc()}")
        return None

def pick_acca(matches, n=5, min_prob=52.0):
    scored = []
    for m in matches:
        l_id = m.get("event", {}).get("league", {}).get("id", 0)
        res  = analyze_match(m, l_id)
        if not res:
            continue
        p = res["rec"]["p"]
        if p < min_prob:
            continue
        scored.append({"match": m, "result": res,
                        "score": p * (res["confidence"] / 100), "league_id": l_id})

    scored.sort(key=lambda x: x["score"], reverse=True)
    picks        = []
    league_count = {}
    for s in scored:
        lg = s["league_id"]
        if league_count.get(lg, 0) >= 2:
            continue
        league_count[lg] = league_count.get(lg, 0) + 1
        picks.append(s)
        if len(picks) >= n:
            break

    combined = 1.0
    for p in picks:
        combined *= p["result"]["rec"]["odds"]
    return picks, round(combined, 2)
