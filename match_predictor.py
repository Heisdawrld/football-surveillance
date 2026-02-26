"""
match_predictor.py — ProPredictor Conviction Engine v3

Philosophy: Don't pick the safest market. Pick the one where the MOST
signals agree. A tip is only worth giving when multiple independent
factors point the same direction. The model is not afraid of high odds
— if data says away win, it says away win.

Each possible tip is scored across 6 independent signals:
  1. Raw probability (from API's own model)
  2. xG signal (who is creating more, and by how much)
  3. Form signal (weighted last-5 results)
  4. Standing gap (league position difference)
  5. Value edge (model prob vs bookmaker implied prob)
  6. Signal agreement (are ALL signals pointing same way?)

A tip wins only when it scores highest ACROSS all signals combined.
Over 1.5 can no longer win just by being a big number — it needs
independent backing from xG, form, and context too.
"""

import math

# ── Poisson utilities ─────────────────────────────────────────────────────────

def poisson_pmf(k, lam):
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return (lam ** k) * math.exp(-lam) / math.factorial(k)

def calculate_likely_score(h_xg, a_xg, over_15_prob=50, max_goals=6):
    scores = []
    for h in range(max_goals + 1):
        for a in range(max_goals + 1):
            p = poisson_pmf(h, h_xg) * poisson_pmf(a, a_xg)
            scores.append((p, h, a))
    scores.sort(reverse=True)
    best_p, best_h, best_a = scores[0]
    if best_h == 0 and best_a == 0 and over_15_prob >= 65:
        for p, h, a in scores:
            if h + a >= 1:
                return f"{h}-{a}"
    return f"{best_h}-{best_a}"

# ── Form utilities ────────────────────────────────────────────────────────────

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
    prob_gap     = fav_prob - (1 - fav_prob)
    stand_diff   = abs((fav_stand or 10) - (dog_stand or 10))
    stand_factor = min(stand_diff / 10, 1.0)
    raw   = (dog_form * 0.4 + stand_factor * 0.3 + (1 - prob_gap) * 0.3)
    index = round(raw * 100, 1)
    if index >= 65 and prob_gap > 0.15:
        return {"index": index, "label": "HIGH UPSET RISK",     "color": "warn"}
    elif index >= 50:
        return {"index": index, "label": "MODERATE UPSET RISK", "color": "blue"}
    else:
        return {"index": index, "label": "LOW UPSET RISK",       "color": "muted"}

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

# ── CONVICTION SCORING ENGINE ─────────────────────────────────────────────────

def _xg_signal_for(tip_key, h_xg, a_xg):
    """
    How strongly does xG support this tip?
    Returns 0.0 – 1.0
    """
    total = max(h_xg + a_xg, 0.1)
    h_dom = h_xg / total   # 0–1, home dominance
    a_dom = a_xg / total

    if tip_key == "HOME WIN":
        # Strong home xG dominance (>60% of total)
        return min(h_dom / 0.6, 1.0) if h_dom > 0.5 else h_dom * 0.5
    elif tip_key == "AWAY WIN":
        return min(a_dom / 0.6, 1.0) if a_dom > 0.5 else a_dom * 0.5
    elif tip_key == "DRAW":
        # xG balance (both close to 50%) supports draw
        balance = 1 - abs(h_dom - 0.5) * 2
        return balance
    elif tip_key in ("OVER 1.5", "OVER 2.5", "OVER 3.5"):
        # Total xG supports overs
        thresholds = {"OVER 1.5": 1.8, "OVER 2.5": 2.4, "OVER 3.5": 3.2}
        t = thresholds[tip_key]
        return min(total / t, 1.0)
    elif tip_key == "BTTS":
        # Both teams need meaningful xG (>0.6 each)
        h_score = min(h_xg / 0.8, 1.0)
        a_score = min(a_xg / 0.8, 1.0)
        return h_score * a_score
    return 0.5

def _form_signal_for(tip_key, h_form, a_form):
    """
    How strongly does recent form support this tip?
    Returns 0.0 – 1.0
    """
    h_f = form_score(h_form)
    a_f = form_score(a_form)

    if tip_key == "HOME WIN":
        # Home form strong, away form weak
        return h_f * (1 - a_f * 0.5)
    elif tip_key == "AWAY WIN":
        return a_f * (1 - h_f * 0.5)
    elif tip_key == "DRAW":
        # Both teams mediocre form, or closely matched
        balance = 1 - abs(h_f - a_f)
        avg     = (h_f + a_f) / 2
        # Draw more likely when both around 0.4–0.6
        mid_factor = 1 - abs(avg - 0.5) * 2
        return (balance * 0.6 + mid_factor * 0.4)
    elif tip_key in ("OVER 1.5", "OVER 2.5", "OVER 3.5"):
        # Attacking form from both sides
        return (h_f + a_f) / 2
    elif tip_key == "BTTS":
        # Both need decent attacking form
        return min(h_f, a_f) * 1.2  # capped at 1.0 later
    return 0.5

def _standing_signal_for(tip_key, h_stand, a_stand, total_teams=20):
    """
    How do league standings support this tip?
    Returns 0.0 – 1.0
    """
    if not h_stand or not a_stand:
        return 0.5  # neutral when unknown

    h_rank = h_stand / total_teams   # 0=top, 1=bottom
    a_rank = a_stand / total_teams
    h_strength = 1 - h_rank          # 1=top, 0=bottom
    a_strength = 1 - a_rank

    if tip_key == "HOME WIN":
        return h_strength * (1 - a_strength * 0.5)
    elif tip_key == "AWAY WIN":
        return a_strength * (1 - h_strength * 0.5)
    elif tip_key == "DRAW":
        return 1 - abs(h_strength - a_strength)
    elif tip_key in ("OVER 1.5", "OVER 2.5"):
        # Top teams tend to score more
        return (h_strength + a_strength) / 2
    elif tip_key == "OVER 3.5":
        return ((h_strength + a_strength) / 2) * 0.8
    elif tip_key == "BTTS":
        return min(h_strength, a_strength)
    return 0.5

def _value_signal(tip_prob, bookie_odds):
    """
    Does the bookmaker UNDERESTIMATE this outcome? That's signal.
    Returns 0.0 – 1.0 (0.5 = neutral, >0.5 = value exists)
    """
    edge = value_edge(tip_prob, bookie_odds)
    if edge is None:
        return 0.5
    # Edge of +5% = strong signal, -5% = weak
    return max(0.0, min(1.0, 0.5 + edge / 20))

def conviction_score(tip_key, prob, bookie_odds,
                     h_xg, a_xg, h_form, a_form,
                     h_stand, a_stand):
    """
    Multi-signal conviction score for a single tip.

    Core problem solved: Over 1.5 has 80-90% raw prob in almost every match,
    so it always wins on raw probability alone. We fix this by:
    
    1. Normalising probability within its market category
       (1X2 vs goals markets compete separately, then winners face off)
    2. Giving 1X2 tips a bonus when signals strongly agree
    3. Penalising goal markets that are "always high" — the INFORMATION
       value of Over 1.5 = 85% is low. Over 2.5 = 72% is more informative.
    
    Weights:
      30% — normalised probability (penalised for uninformative markets)
      28% — xG signal
      22% — form signal  
      12% — standing signal
      8%  — value edge
    """
    s_xg       = _xg_signal_for(tip_key, h_xg, a_xg)
    s_form     = min(_form_signal_for(tip_key, h_form, a_form), 1.0)
    s_standing = _standing_signal_for(tip_key, h_stand, a_stand)
    s_value    = _value_signal(prob, bookie_odds)

    # Normalise probability — penalise markets that are "always high"
    # Over 1.5 at 85% is boring. Home Win at 65% is meaningful.
    if tip_key == "OVER 1.5":
        # Scale: 60% prob = 0.0 signal, 95% prob = 1.0 signal
        # So 85% becomes (85-60)/(95-60) = 0.71 — not automatic winner
        s_prob = max(0.0, (prob - 60) / 35)
    elif tip_key == "OVER 2.5":
        # Scale: 40% = 0.0, 80% = 1.0
        s_prob = max(0.0, (prob - 40) / 40)
    elif tip_key == "OVER 3.5":
        # Scale: 20% = 0.0, 60% = 1.0
        s_prob = max(0.0, (prob - 20) / 40)
    elif tip_key == "BTTS":
        # Scale: 40% = 0.0, 75% = 1.0
        s_prob = max(0.0, (prob - 40) / 35)
    else:
        # 1X2: raw probability is meaningful — Home Win 65% IS significant
        s_prob = prob / 100

    raw = (s_prob     * 0.30 +
           s_xg       * 0.28 +
           s_form     * 0.22 +
           s_standing * 0.12 +
           s_value    * 0.08)

    return round(raw * 100, 2)

def _agreement_count(tip_key, h_xg, a_xg, h_form, a_form, h_stand, a_stand):
    """
    How many independent signals agree with this tip?
    Returns int 0–4 (xG, form, standing, each counted if signal >= 0.55)
    """
    signals = [
        _xg_signal_for(tip_key, h_xg, a_xg),
        _form_signal_for(tip_key, h_form, a_form),
        _standing_signal_for(tip_key, h_stand, a_stand),
    ]
    return sum(1 for s in signals if s >= 0.55)

# ── Tip reason generator ──────────────────────────────────────────────────────

def _build_reason(tip_key, h_xg, a_xg, h_form, a_form,
                  h_stand, a_stand, prob, bookie_odds, h_name, a_name):
    """
    Generate a short 1-line reason why this tip was selected.
    Picks the STRONGEST signal and writes a human sentence about it.
    """
    signals = {
        "xG":      _xg_signal_for(tip_key, h_xg, a_xg),
        "form":    min(_form_signal_for(tip_key, h_form, a_form), 1.0),
        "standing":_standing_signal_for(tip_key, h_stand, a_stand),
    }
    top_signal = max(signals, key=signals.get)
    edge       = value_edge(prob, bookie_odds)
    edge_str   = f" — market underpricing by {edge}%" if edge and edge > 3 else ""

    h = h_name.split()[0]
    a = a_name.split()[0]

    reasons = {
        ("xG", "HOME WIN"):   f"{h} generating significantly more xG ({h_xg} vs {a_xg}){edge_str}",
        ("xG", "AWAY WIN"):   f"{a} outperforming on xG ({a_xg} vs {h_xg}), strong away threat{edge_str}",
        ("xG", "DRAW"):       f"xG almost identical ({h_xg} vs {a_xg}), balanced match expected{edge_str}",
        ("xG", "OVER 1.5"):   f"Combined xG of {round(h_xg+a_xg,2)} makes goals highly probable{edge_str}",
        ("xG", "OVER 2.5"):   f"High combined xG ({round(h_xg+a_xg,2)}) supports a multi-goal game{edge_str}",
        ("xG", "OVER 3.5"):   f"Both teams creating heavily — xG total {round(h_xg+a_xg,2)} backs goals{edge_str}",
        ("xG", "BTTS"):       f"Both teams generating real chances — {h} {h_xg} xG, {a} {a_xg} xG{edge_str}",
        ("form", "HOME WIN"):  f"{h} in strong form, {a} struggling recently{edge_str}",
        ("form", "AWAY WIN"):  f"{a} arriving in excellent form, {h} dropping points lately{edge_str}",
        ("form", "DRAW"):      f"Both sides drawing frequently — form points to stalemate{edge_str}",
        ("form", "OVER 1.5"):  f"Both teams scoring consistently in recent games{edge_str}",
        ("form", "OVER 2.5"):  f"Recent fixtures for both sides have been high-scoring{edge_str}",
        ("form", "OVER 3.5"):  f"Form trend shows both teams involved in goals regularly{edge_str}",
        ("form", "BTTS"):      f"Both teams have been scoring in nearly every game recently{edge_str}",
        ("standing","HOME WIN"):f"{h} significantly higher in standings (#{h_stand} vs #{a_stand}){edge_str}",
        ("standing","AWAY WIN"):f"{a} punching above their odds — #{a_stand} vs #{h_stand} in table{edge_str}",
        ("standing","DRAW"):    f"Closely matched on standings (#{h_stand} vs #{a_stand}){edge_str}",
        ("standing","OVER 1.5"):f"Both quality sides expected to create chances{edge_str}",
        ("standing","OVER 2.5"):f"Table positions suggest an open, attacking game{edge_str}",
        ("standing","OVER 3.5"):f"Both sides near top — high-quality, open encounter expected{edge_str}",
        ("standing","BTTS"):    f"Neither side likely to keep a clean sheet given table positions{edge_str}",
    }
    key = (top_signal, tip_key)
    return reasons.get(key, f"{prob}% probability backed by multiple data signals{edge_str}")

# ── Combo tip builder ─────────────────────────────────────────────────────────

def _build_combo_tips(h_win, draw, a_win, o15, o25, btts,
                      h_xg, a_xg, h_form, a_form, h_stand, a_stand,
                      odds_h, odds_a, odds_o25, odds_btts,
                      h_name, a_name):
    """
    Build risky combo tips from joint probabilities.
    Joint P(A and B) = P(A) * P(B) assuming independence (approximate).
    Only combos where joint prob >= 30% and conviction is high.
    """
    combos = []

    # All possible combos
    candidates = [
        # label,                    p1,          p2,          odds1,  odds2
        ("HOME WIN + BTTS",          h_win/100,   btts/100,    odds_h, odds_btts),
        ("AWAY WIN + BTTS",          a_win/100,   btts/100,    odds_a, odds_btts),
        ("HOME WIN + OVER 2.5",      h_win/100,   o25/100,     odds_h, odds_o25),
        ("AWAY WIN + OVER 2.5",      a_win/100,   o25/100,     odds_a, odds_o25),
        ("OVER 2.5 + BTTS",          o25/100,     btts/100,    odds_o25, odds_btts),
        ("OVER 1.5 + BTTS",          o15/100,     btts/100,    None,   odds_btts),
        ("DRAW + BTTS",              draw/100,    btts/100,    None,   odds_btts),
    ]

    for label, p1, p2, o1, o2 in candidates:
        joint_prob = round(p1 * p2 * 100, 1)
        if joint_prob < 28:
            continue

        # Combo fair odds = product of fair odds for each part
        fair_o1 = round(1 / max(p1, 0.01), 2)
        fair_o2 = round(1 / max(p2, 0.01), 2)
        combo_fair_odds = round(fair_o1 * fair_o2, 2)

        # Quick agreement check: do xG and form both support this?
        parts = label.split(" + ")
        agreement = 0
        for part in parts:
            # Map combo part to signal key
            sig_key = part.strip()
            xg_s  = _xg_signal_for(sig_key, h_xg, a_xg)
            frm_s = min(_form_signal_for(sig_key, h_form, a_form), 1.0)
            if xg_s >= 0.5 and frm_s >= 0.5:
                agreement += 1

        if agreement < 1:
            continue

        combos.append({
            "label":      label,
            "prob":       joint_prob,
            "fair_odds":  combo_fair_odds,
            "agreement":  agreement,
        })

    # Sort by joint probability * agreement
    combos.sort(key=lambda x: x["prob"] * x["agreement"], reverse=True)
    return combos[:3] if combos else []

# ── Safe alternate picker ─────────────────────────────────────────────────────

def _pick_safe_alternate(main_tip, tip_scores, h_xg, a_xg, btts, o15, o25):
    """
    Pick the safest credible alternate tip that:
    - is different from the main tip
    - has genuine backing (not just a big number)
    - provides real alternative value
    """
    # Exclude main tip and build safe candidates
    safe_priority = []

    for tip, score in sorted(tip_scores.items(), key=lambda x: x[1], reverse=True):
        if tip == main_tip:
            continue

        # Over 1.5 is safe only if xG genuinely supports it
        if tip == "OVER 1.5":
            total_xg = h_xg + a_xg
            if total_xg < 1.6:
                continue  # don't recommend Over 1.5 when xG doesn't back it

        # Over 2.5 as safe — only if o25 > 55 AND xG supports
        if tip == "OVER 2.5":
            if o25 < 55 or (h_xg + a_xg) < 2.2:
                continue

        # BTTS as safe — only if both teams have meaningful xG
        if tip == "BTTS":
            if h_xg < 0.7 or a_xg < 0.7:
                continue

        safe_priority.append((tip, score))

    if not safe_priority:
        # Fallback: just pick second-highest conviction that isn't main
        fallback = [(t, s) for t, s in tip_scores.items() if t != main_tip]
        fallback.sort(key=lambda x: x[1], reverse=True)
        return fallback[0] if fallback else ("OVER 1.5", 50.0)

    return safe_priority[0]

# ── Main analysis ─────────────────────────────────────────────────────────────

def analyze_match(api_data, league_id=None):
    try:
        event  = api_data.get("event", {})
        league = event.get("league", {})
        l_id   = league_id or league.get("id", 1)
        h_name = event.get("home_team", "Home")
        a_name = event.get("away_team", "Away")

        # ── Raw probabilities from API ──
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
        likely = calculate_likely_score(h_xg, a_xg, o15)

        # ── Bookmaker odds ──
        odds_h    = event.get("odds_home")
        odds_d    = event.get("odds_draw")
        odds_a    = event.get("odds_away")
        odds_o15  = event.get("odds_over_15")
        odds_o25  = event.get("odds_over_25")
        odds_btts = event.get("odds_btts_yes")

        # ── Team context ──
        h_form  = api_data.get("home_form", [])
        a_form  = api_data.get("away_form", [])
        h_stand = api_data.get("home_standing")
        a_stand = api_data.get("away_standing")

        # ── CONVICTION SCORING for every tip ──
        tip_probs = {
            "HOME WIN":  h_win,
            "AWAY WIN":  a_win,
            "DRAW":      draw,
            "OVER 1.5":  o15,
            "OVER 2.5":  o25,
            "OVER 3.5":  o35,
            "BTTS":      btts,
        }
        tip_odds = {
            "HOME WIN":  odds_h,
            "AWAY WIN":  odds_a,
            "DRAW":      odds_d,
            "OVER 1.5":  odds_o15,
            "OVER 2.5":  odds_o25,
            "OVER 3.5":  None,
            "BTTS":      odds_btts,
        }

        tip_scores = {}
        tip_agreements = {}
        for tip, prob in tip_probs.items():
            tip_scores[tip] = conviction_score(
                tip, prob, tip_odds.get(tip),
                h_xg, a_xg, h_form, a_form, h_stand, a_stand
            )
            tip_agreements[tip] = _agreement_count(
                tip, h_xg, a_xg, h_form, a_form, h_stand, a_stand
            )

        # ── Main tip = highest conviction ──
        main_tip  = max(tip_scores, key=tip_scores.get)
        main_prob = tip_probs[main_tip]
        main_conv = tip_scores[main_tip]
        main_odds = round(100 / max(main_prob, 1), 2)
        main_edge = value_edge(main_prob, tip_odds.get(main_tip))
        main_agree = tip_agreements[main_tip]
        main_reason = _build_reason(
            main_tip, h_xg, a_xg, h_form, a_form,
            h_stand, a_stand, main_prob, tip_odds.get(main_tip),
            h_name, a_name
        )

        # ── Safe alternate ──
        safe_tip, safe_conv = _pick_safe_alternate(
            main_tip, tip_scores, h_xg, a_xg, btts, o15, o25
        )
        safe_prob  = tip_probs[safe_tip]
        safe_odds  = round(100 / max(safe_prob, 1), 2)
        safe_edge  = value_edge(safe_prob, tip_odds.get(safe_tip))
        safe_reason = _build_reason(
            safe_tip, h_xg, a_xg, h_form, a_form,
            h_stand, a_stand, safe_prob, tip_odds.get(safe_tip),
            h_name, a_name
        )

        # ── Risky combo ──
        combos = _build_combo_tips(
            h_win, draw, a_win, o15, o25, btts,
            h_xg, a_xg, h_form, a_form, h_stand, a_stand,
            odds_h, odds_a, odds_o25, odds_btts,
            h_name, a_name
        )
        risky = combos[0] if combos else {
            "label":     f"{main_tip} + BTTS",
            "prob":      round(main_prob * btts / 100, 1),
            "fair_odds": round(main_odds * round(100/max(btts,1), 2), 2),
            "agreement": 0,
        }

        # ── Tag based on conviction + agreement ──
        if main_conv >= 65 and main_agree >= 2:
            tag = "ELITE VALUE"
        elif main_conv >= 55 and main_agree >= 1:
            tag = "STRONG PICK"
        elif main_conv >= 45:
            tag = "QUANT EDGE"
        else:
            tag = "MONITOR"

        return {
            "tag":          tag,
            "xg_h":         round(h_xg, 2),
            "xg_a":         round(a_xg, 2),
            "likely_score": likely,
            "1x2":          {"home": round(h_win,1), "draw": round(draw,1), "away": round(a_win,1)},
            "markets":      {
                "over_15":  round(o15,1),
                "over_25":  round(o25,1),
                "over_35":  round(o35,1),
                "under_25": round(100-o25,1),
                "btts":     round(btts,1),
            },
            # Three-tier tip structure
            "main": {
                "tip":      main_tip,
                "prob":     round(main_prob, 1),
                "odds":     main_odds,
                "edge":     main_edge,
                "conv":     main_conv,
                "agree":    main_agree,    # how many signals agree (0-3)
                "reason":   main_reason,
            },
            "safe": {
                "tip":      safe_tip,
                "prob":     round(safe_prob, 1),
                "odds":     safe_odds,
                "edge":     safe_edge,
                "reason":   safe_reason,
            },
            "risky": {
                "tip":      risky["label"],
                "prob":     risky["prob"],
                "odds":     risky["fair_odds"],
            },
            # Legacy keys so app.py doesn't break
            "rec":     {"t": main_tip,  "p": round(main_prob,1),  "odds": main_odds,  "edge": main_edge},
            "second":  {"t": safe_tip,  "p": round(safe_prob,1)},
            "confidence":   round(conf, 1),
            "momentum":     momentum_score(h_form, a_form, h_xg, a_xg),
            "upset":        upset_index(h_win, a_win, h_form, a_form, h_stand, a_stand),
            "style":        style_profile(h_xg, a_xg, o25, btts),
            "form":         {"home": list(h_form)[-5:], "away": list(a_form)[-5:]},
            "standings":    {"home": h_stand, "away": a_stand},
        }

    except Exception as e:
        import traceback
        print(f"[Predictor Error] {e}\n{traceback.format_exc()}")
        return None

# ── ACCA builder ──────────────────────────────────────────────────────────────

def pick_acca(matches, n=5, min_conv=42.0):
    """
    Select top N picks using conviction score, not raw probability.
    This means the ACCA won't just be 5x Over 1.5.
    """
    scored = []
    for m in matches:
        l_id = m.get("event", {}).get("league", {}).get("id", 0)
        res  = analyze_match(m, l_id)
        if not res:
            continue
        conv = res["main"]["conv"]
        if conv < min_conv:
            continue
        scored.append({
            "match":     m,
            "result":    res,
            "conv":      conv,
            "league_id": l_id,
        })

    scored.sort(key=lambda x: x["conv"], reverse=True)
    picks        = []
    league_count = {}
    tip_count    = {}  # also diversify tips — max 2 of same tip type

    for s in scored:
        lg  = s["league_id"]
        tip = s["result"]["main"]["tip"]
        if league_count.get(lg, 0) >= 2:
            continue
        if tip_count.get(tip, 0) >= 2:
            continue
        league_count[lg]  = league_count.get(lg, 0) + 1
        tip_count[tip]    = tip_count.get(tip, 0) + 1
        picks.append(s)
        if len(picks) >= n:
            break

    combined = 1.0
    for p in picks:
        combined *= p["result"]["main"]["odds"]
    return picks, round(combined, 2)
