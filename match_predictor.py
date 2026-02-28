"""
match_predictor.py  --  ProPredictor GOD MODE v5

Architecture:
  1. xG Calibration     — form trend × standing × team profile from DB
  2. Full Poisson Matrix — every scoreline computed, all 50+ markets derived
  3. Conviction Engine   — per-market normalisation prevents Over 1.5 from
                           always beating a meaningful 1X2 tip
  4. Human Variance      — form streaks, luck correction, head-to-head memory
  5. Best-of-3 Output    — Recommended · Safest · Risky (always distinct)
  6. Intelligent Tag     — SURE / RELIABLE / SOLID / VOLATILE / AVOID / MONITOR

The model never defaults. If data is thin, conviction is low → MONITOR tag.
"""

import math, sys

try:
    import database as _db
    _HAS_DB = True
except ImportError:
    _HAS_DB = False

_cal_cache = {"d": {}, "t": 0}

def _calibration():
    import time
    if time.time() - _cal_cache["t"] > 3600 and _HAS_DB:
        try: _cal_cache["d"] = _db.get_market_calibration(); _cal_cache["t"] = time.time()
        except: pass
    return _cal_cache["d"]

# ─────────────────────────────────────────────────────────────────────────────
# POISSON CORE
# ─────────────────────────────────────────────────────────────────────────────

def _pmf(k, lam):
    if lam <= 0: return 1.0 if k == 0 else 0.0
    return (lam**k) * math.exp(-lam) / math.factorial(k)

def _full_market_matrix(xg_h, xg_a, cap=9):
    """
    Compute every scoreline probability then derive ALL 50+ markets.
    Single pass — called once per match.
    """
    hw = dw = aw = 0.0
    o05=o15=o25=o35=o45=o55 = 0.0
    gg = ng = 0.0
    h05=h15 = 0.0    # home team goals
    a05=a15 = 0.0    # away team goals
    hcs=acs  = 0.0   # clean sheets (home keeps / away keeps)
    odd=even = 0.0

    for hg in range(cap+1):
        ph = _pmf(hg, xg_h)
        for ag in range(cap+1):
            pa = _pmf(ag, xg_a)
            p  = ph * pa
            t  = hg + ag
            if hg > ag:    hw += p
            elif hg == ag: dw += p
            else:          aw += p
            if t > 0: o05 += p
            if t > 1: o15 += p
            if t > 2: o25 += p
            if t > 3: o35 += p
            if t > 4: o45 += p
            if t > 5: o55 += p
            if hg > 0 and ag > 0: gg += p
            if hg > 0: h05 += p
            if hg > 1: h15 += p
            if ag > 0: a05 += p
            if ag > 1: a15 += p
            if ag == 0: hcs += p   # home clean sheet = away scored 0
            if hg == 0: acs += p   # away clean sheet = home scored 0
            if t % 2 == 1: odd += p
            else:          even += p

    def p(v): return round(min(v * 100, 99.9), 1)
    def ip(v): return round(max((1 - v) * 100, 0.1), 1)

    # HT approximation (45% of xG each half)
    ht_xg_h = xg_h * 0.45; ht_xg_a = xg_a * 0.45
    ht_hw=ht_dw=ht_aw=ht_o05=ht_o15 = 0.0
    for hg in range(6):
        ph = _pmf(hg, ht_xg_h)
        for ag in range(6):
            pa = _pmf(ag, ht_xg_a); pp = ph*pa
            if hg>ag: ht_hw+=pp
            elif hg==ag: ht_dw+=pp
            else: ht_aw+=pp
            if hg+ag>0: ht_o05+=pp
            if hg+ag>1: ht_o15+=pp

    # 2H: total minus HT approximation
    sh_xg_h = xg_h * 0.55; sh_xg_a = xg_a * 0.55
    sh_hw=sh_dw=sh_aw=sh_o05=sh_o15 = 0.0
    for hg in range(7):
        ph = _pmf(hg, sh_xg_h)
        for ag in range(7):
            pa = _pmf(ag, sh_xg_a); pp = ph*pa
            if hg>ag: sh_hw+=pp
            elif hg==ag: sh_dw+=pp
            else: sh_aw+=pp
            if hg+ag>0: sh_o05+=pp
            if hg+ag>1: sh_o15+=pp

    # Win Either Half
    h_weh = min(hw * 1.40, 0.97); a_weh = min(aw * 1.40, 0.94)
    # Draw No Bet
    dnb_h = hw / max(hw+aw, 0.001); dnb_a = aw / max(hw+aw, 0.001)
    # Asian handicap -0.5 = same as win, +0.5 = win or draw
    hc_h05  = hw; hc_a05 = aw   # -0.5 handicap: need to win
    hc_h_05 = hw+dw; hc_a_05 = aw+dw  # +0.5: win or draw

    return {
        # 1X2
        "HOME WIN":               p(hw),
        "DRAW":                   p(dw),
        "AWAY WIN":               p(aw),
        # Goals totals
        "OVER 0.5":               p(o05),
        "OVER 1.5":               p(o15),
        "OVER 2.5":               p(o25),
        "OVER 3.5":               p(o35),
        "OVER 4.5":               p(o45),
        "OVER 5.5":               p(o55),
        "UNDER 0.5":              ip(o05),
        "UNDER 1.5":              ip(o15),
        "UNDER 2.5":              ip(o25),
        "UNDER 3.5":              ip(o35),
        "UNDER 4.5":              ip(o45),
        "UNDER 5.5":              ip(o55),
        # BTTS
        "GG":                     p(gg),
        "NG":                     p(1-gg),
        # Double Chance
        "DOUBLE CHANCE 1X":       p(hw+dw),
        "DOUBLE CHANCE X2":       p(dw+aw),
        "DOUBLE CHANCE 12":       p(hw+aw),
        # Draw No Bet
        "DNB HOME":               p(dnb_h),
        "DNB AWAY":               p(dnb_a),
        # Team goals
        "HOME OVER 0.5":          p(h05),
        "HOME UNDER 0.5":         ip(h05),
        "HOME OVER 1.5":          p(h15),
        "HOME UNDER 1.5":         ip(h15),
        "AWAY OVER 0.5":          p(a05),
        "AWAY UNDER 0.5":         ip(a05),
        "AWAY OVER 1.5":          p(a15),
        "AWAY UNDER 1.5":         ip(a15),
        # Clean sheets
        "HOME CLEAN SHEET":       p(hcs),
        "HOME NO CLEAN SHEET":    ip(hcs),
        "AWAY CLEAN SHEET":       p(acs),
        "AWAY NO CLEAN SHEET":    ip(acs),
        # Either half
        "HOME WIN EITHER HALF":   p(h_weh),
        "AWAY WIN EITHER HALF":   p(a_weh),
        # 1st Half
        "HT HOME WIN":            p(ht_hw),
        "HT DRAW":                p(ht_dw),
        "HT AWAY WIN":            p(ht_aw),
        "HT OVER 0.5":            p(ht_o05),
        "HT OVER 1.5":            p(ht_o15),
        "HT UNDER 1.5":           ip(ht_o15),
        # 2nd Half
        "2H HOME WIN":            p(sh_hw),
        "2H DRAW":                p(sh_dw),
        "2H AWAY WIN":            p(sh_aw),
        "2H OVER 0.5":            p(sh_o05),
        "2H OVER 1.5":            p(sh_o15),
        "2H UNDER 1.5":           ip(sh_o15),
        # Asian Handicap
        "HANDICAP HOME -0.5":     p(hc_h05),
        "HANDICAP AWAY -0.5":     p(hc_a05),
        "HANDICAP HOME +0.5":     p(hc_h_05),
        "HANDICAP AWAY +0.5":     p(hc_a_05),
        # Odd / Even
        "ODD GOALS":              p(odd),
        "EVEN GOALS":             p(even),
    }

# ─────────────────────────────────────────────────────────────────────────────
# FORM & MOMENTUM
# ─────────────────────────────────────────────────────────────────────────────

FORM_W = [1.0, 1.2, 1.4, 1.6, 1.8]
FORM_V = {"W": 1.0, "D": 0.4, "L": 0.0}

def form_score(form):
    if not form: return 0.5
    results = [r.upper() for r in list(form)[-5:] if r.upper() in ("W","D","L")]
    if not results: return 0.5
    ws = FORM_W[-len(results):]
    return round(sum(FORM_V[r]*w for r,w in zip(results,ws)) / sum(ws), 4)

def form_trend(form):
    if not form: return "STABLE"
    results = [r.upper() for r in list(form)[-5:] if r.upper() in ("W","D","L")]
    if len(results) < 3: return "STABLE"
    vals = [FORM_V[r] for r in results]
    diff = sum(vals[-2:])/2 - sum(vals[:2])/2
    if diff >  0.25: return "RISING"
    if diff < -0.25: return "FALLING"
    return "STABLE"

def momentum_score(h_form, a_form, xg_h, xg_a):
    hf = form_score(h_form); af = form_score(a_form)
    tot = max(xg_h+xg_a, 0.1)
    hm = round((hf*0.6 + xg_h/tot*0.4)*100, 1)
    am = round((af*0.6 + xg_a/tot*0.4)*100, 1)
    ht = form_trend(h_form); at_ = form_trend(a_form)
    gap = abs(hm-am)
    if gap < 8:    narr = "Momentum evenly balanced"
    elif hm > am:  narr = f"Home side carrying momentum ({ht.lower()} form)"
    else:          narr = f"Away side the in-form team ({at_.lower()} trajectory)"
    return {"home":hm,"away":am,"h_trend":ht,"a_trend":at_,"narrative":narr}

def style_profile(xg_h, xg_a, btts):
    t = xg_h+xg_a
    if t >= 3.0:   s = "High-scoring encounter — both teams creating freely"
    elif t >= 2.2: s = "Open game — goals expected from both ends"
    elif t >= 1.5: s = "Balanced contest — goals possible but not guaranteed"
    else:          s = "Defensive battle — one goal could settle it"
    if btts >= 65:  s += " · Both teams likely to score"
    elif btts <= 35: s += " · Clean sheet possible"
    return s

def value_edge(prob, bookie_odds):
    if not bookie_odds or bookie_odds <= 1.0: return None
    return round((prob/100 - 1/bookie_odds)*100, 1)

# ─────────────────────────────────────────────────────────────────────────────
# xG CALIBRATION — the intelligence layer
# ─────────────────────────────────────────────────────────────────────────────

def calibrate_xg(base_h, base_a, h_form, a_form, h_stand, a_stand,
                 h_profile=None, a_profile=None, h_luck=0.0, a_luck=0.0):
    """
    Adjust raw xG using every available intelligence signal.
    Returns (adj_xg_h, adj_xg_a, data_confidence 0-1).

    data_confidence rises with each available signal:
      0.0 = pure default (no data)
      0.4 = standings only
      0.6 = form + standings
      0.8 = form + standings + H2H
      1.0 = all signals + DB profile
    """
    xg_h = base_h; xg_a = base_a
    confidence = 0.0

    # ── Form adjustment ───────────────────────────────────────────────────────
    hf = form_score(h_form); af = form_score(a_form)
    ht = form_trend(h_form); at_ = form_trend(a_form)
    has_form = len([r for r in (h_form or []) if r.upper() in ("W","D","L")]) >= 3

    if has_form:
        confidence += 0.3
        # Form score: 0.5 = neutral, 0 = terrible, 1 = perfect
        # Scale: form score of 1.0 → +28% xG; 0.0 → -28%
        xg_h *= (0.72 + hf * 0.56)
        xg_a *= (0.72 + af * 0.56)
        # Trend momentum bonus/penalty
        if ht == "RISING":    xg_h *= 1.12
        elif ht == "FALLING": xg_h *= 0.88
        if at_ == "RISING":   xg_a *= 1.12
        elif at_ == "FALLING": xg_a *= 0.88

    # ── Luck correction ───────────────────────────────────────────────────────
    # h_luck = goals_scored - expected_goals for recent matches
    # Positive luck means they overperformed → regress toward xG
    if abs(h_luck) > 0.2:
        xg_h *= (1.0 - h_luck * 0.12)   # overcorrect positive luck downward
    if abs(a_luck) > 0.2:
        xg_a *= (1.0 - a_luck * 0.12)

    # ── Standing adjustment ───────────────────────────────────────────────────
    if h_stand:
        confidence += 0.15
        if h_stand <= 3:    xg_h *= 1.20
        elif h_stand <= 6:  xg_h *= 1.10
        elif h_stand <= 10: xg_h *= 1.02
        elif h_stand >= 17: xg_h *= 0.84
        elif h_stand >= 13: xg_h *= 0.93

    if a_stand:
        confidence += 0.15
        if a_stand <= 3:    xg_a *= 1.20
        elif a_stand <= 6:  xg_a *= 1.10
        elif a_stand <= 10: xg_a *= 1.02
        elif a_stand >= 17: xg_a *= 0.84
        elif a_stand >= 13: xg_a *= 0.93

    # ── Team profile from DB (real settled data) ──────────────────────────────
    if h_profile and h_profile.get("played", 0) >= 5:
        confidence += 0.20
        played  = h_profile["played"]
        blend   = min(0.48, played * 0.024)
        xg_h    = round(xg_h*(1-blend) + h_profile["avg_scored"]*blend, 3)
        db = min(0.32, played * 0.016)
        xg_a    = round(xg_a*(1-db)    + h_profile["avg_conceded"]*db,  3)

    if a_profile and a_profile.get("played", 0) >= 5:
        confidence += 0.20
        played  = a_profile["played"]
        blend   = min(0.48, played * 0.024)
        xg_a    = round(xg_a*(1-blend) + a_profile["avg_scored"]*blend, 3)
        db = min(0.32, played * 0.016)
        xg_h    = round(xg_h*(1-db)    + a_profile["avg_conceded"]*db,  3)

    return round(max(xg_h, 0.22), 3), round(max(xg_a, 0.16), 3), min(confidence, 1.0)

# ─────────────────────────────────────────────────────────────────────────────
# CONVICTION SCORING
# ─────────────────────────────────────────────────────────────────────────────

# (min_baseline, max_ceiling) for probability normalisation per market
# Markets with naturally high baselines get squeezed so they compete fairly
_NORMS = {
    "HOME WIN":               (28, 80), "DRAW":             (18, 42),
    "AWAY WIN":               (20, 70), "OVER 0.5":         (86, 99),
    "OVER 1.5":               (68, 96), "OVER 2.5":         (40, 82),
    "OVER 3.5":               (16, 56), "OVER 4.5":         (6,  32),
    "OVER 5.5":               (2,  16), "UNDER 1.5":        (4,  30),
    "UNDER 2.5":              (18, 60), "UNDER 3.5":        (44, 84),
    "GG":                     (38, 76), "NG":               (24, 62),
    "DOUBLE CHANCE 1X":       (52, 92), "DOUBLE CHANCE X2": (42, 88),
    "DOUBLE CHANCE 12":       (60, 95), "DNB HOME":         (38, 85),
    "DNB AWAY":               (28, 78), "HOME OVER 0.5":    (65, 94),
    "HOME OVER 1.5":          (32, 70), "HOME UNDER 0.5":   (6,  35),
    "HOME UNDER 1.5":         (30, 68), "AWAY OVER 0.5":    (52, 88),
    "AWAY OVER 1.5":          (20, 60), "AWAY UNDER 0.5":   (12, 48),
    "AWAY UNDER 1.5":         (40, 80), "HOME CLEAN SHEET": (18, 55),
    "AWAY CLEAN SHEET":       (10, 42), "HOME WIN EITHER HALF": (28, 76),
    "AWAY WIN EITHER HALF":   (16, 62), "HT HOME WIN":      (18, 52),
    "HT DRAW":                (28, 58), "HT AWAY WIN":      (13, 44),
    "HT OVER 0.5":            (48, 88), "HT OVER 1.5":      (16, 50),
    "2H OVER 0.5":            (55, 92), "2H OVER 1.5":      (25, 62),
    "ODD GOALS":              (44, 58), "EVEN GOALS":       (42, 56),
}

def _norm(tip, prob):
    lo, hi = _NORMS.get(tip, (25, 85))
    return max(0.0, min(1.0, (prob-lo)/max(hi-lo, 1)))

def _xg_sig(tip, xg_h, xg_a):
    """How strongly does the xG ratio support this market?"""
    tot = max(xg_h+xg_a, 0.1)
    hd  = xg_h/tot; ad = xg_a/tot
    t   = tip.upper()
    if "HOME WIN" in t and "EITHER" not in t:
        return min(hd/0.58, 1.0) if hd > 0.5 else hd*0.65
    if "AWAY WIN" in t and "EITHER" not in t:
        return min(ad/0.58, 1.0) if ad > 0.5 else ad*0.65
    if "DRAW" in t and "DNB" not in t and "NO BET" not in t:
        return max(0, 1 - abs(hd-0.5)*2.4)
    if t == "GG":
        return min(xg_h/0.75, 1.0) * min(xg_a/0.75, 1.0)
    if t == "NG":
        return max(0, 1 - min(xg_h/0.75,1)*min(xg_a/0.75,1))
    if "OVER" in t:
        thr = {"OVER 0.5":0.55,"OVER 1.5":1.55,"OVER 2.5":2.25,
               "OVER 3.5":3.1,"OVER 4.5":4.0,"OVER 5.5":5.0,
               "HT OVER 0.5":0.35,"HT OVER 1.5":0.9,
               "HOME OVER 0.5":0.45,"HOME OVER 1.5":1.1,
               "AWAY OVER 0.5":0.35,"AWAY OVER 1.5":0.85,
               "2H OVER 0.5":0.5,"2H OVER 1.5":1.3}.get(t, 2.25)
        return min(tot/thr, 1.0)
    if "UNDER" in t:
        thr = {"UNDER 1.5":1.4,"UNDER 2.5":2.3,"UNDER 3.5":3.2,
               "HOME UNDER 0.5":0.4,"HOME UNDER 1.5":1.0,
               "AWAY UNDER 0.5":0.3,"AWAY UNDER 1.5":0.8,
               "HT UNDER 1.5":0.9,"2H UNDER 1.5":1.2}.get(t, 2.3)
        return max(0, 1 - tot/thr)
    if "CLEAN SHEET" in t:
        return max(0, 1-(xg_a/1.1)) if "HOME" in t else max(0, 1-(xg_h/1.1))
    if "EITHER HALF" in t:
        return min(hd/0.55,1.0) if "HOME" in t else min(ad/0.55,1.0)
    if "DNB HOME" in t or "NO BET" in t and "HOME" in t: return min(hd/0.55,1.0)
    if "DNB AWAY" in t or "NO BET" in t and "AWAY" in t: return min(ad/0.55,1.0)
    if "DOUBLE CHANCE 1X" in t: return max(hd, 0.5)
    if "DOUBLE CHANCE X2" in t: return max(ad, 0.5)
    if "DOUBLE CHANCE 12" in t: return abs(hd-ad)
    return 0.5

def _form_sig(tip, h_form, a_form):
    hf = form_score(h_form); af = form_score(a_form)
    t  = tip.upper()
    if "HOME WIN" in t and "EITHER" not in t: return hf*(1-af*0.5)
    if "AWAY WIN" in t and "EITHER" not in t: return af*(1-hf*0.5)
    if "DRAW" in t and "DNB" not in t: return max(0, 1-abs(hf-af))*0.8
    if "GG" in t or "OVER" in t: return (hf+af)/2
    if "NG" in t or "UNDER" in t: return 1-(hf+af)/2
    if "CLEAN SHEET" in t:
        return (1-af*0.8) if "HOME" in t else (1-hf*0.8)
    if "DOUBLE CHANCE 1X" in t: return hf
    if "DOUBLE CHANCE X2" in t: return af
    if "DNB HOME" in t: return hf
    if "DNB AWAY" in t: return af
    if "EITHER HALF" in t:
        return hf if "HOME" in t else af
    return 0.5

def _stand_sig(tip, h_stand, a_stand, n=20):
    if not h_stand or not a_stand: return 0.5
    hs = 1-h_stand/n; as_ = 1-a_stand/n
    t  = tip.upper()
    if "HOME WIN" in t and "EITHER" not in t: return hs*(1-as_*0.5)
    if "AWAY WIN" in t and "EITHER" not in t: return as_*(1-hs*0.5)
    if "DRAW" in t and "DNB" not in t: return max(0, 1-abs(hs-as_))
    if "OVER" in t or "GG" in t: return (hs+as_)/2
    if "UNDER" in t or "NG" in t: return 1-(hs+as_)/2
    if "CLEAN SHEET" in t:
        return hs*0.8 if "HOME" in t else as_*0.8
    return 0.5

def conviction(tip, prob, xg_h, xg_a, h_form, a_form, h_stand, a_stand,
               bookie_odds=None, data_conf=0.5):
    """
    Returns conviction score 0-100.
    data_conf: 0=no real data, 1=full data. Scales conviction range.
    """
    sp = _norm(tip, prob)
    sx = _xg_sig(tip, xg_h, xg_a)
    sf = min(_form_sig(tip, h_form, a_form), 1.0)
    ss = _stand_sig(tip, h_stand, a_stand)

    sv = 0.5
    if bookie_odds and bookie_odds > 1.0:
        edge = (prob/100) - (1/bookie_odds)
        sv   = max(0.0, min(1.0, 0.5 + edge/0.14))

    raw = sp*0.32 + sx*0.28 + sf*0.20 + ss*0.12 + sv*0.08
    score = round(raw*100, 2)

    # Trend momentum boost/penalty
    ht = form_trend(h_form); at_ = form_trend(a_form)
    t  = tip.upper()
    if "HOME WIN" in t and ht == "RISING" and at_ != "RISING":
        score = min(score*1.12, 100)
    elif "HOME WIN" in t and ht == "FALLING":
        score *= 0.88
    elif "AWAY WIN" in t and at_ == "RISING" and ht != "RISING":
        score = min(score*1.12, 100)
    elif "AWAY WIN" in t and at_ == "FALLING":
        score *= 0.88
    elif "UNDER" in t and ht == "FALLING" and at_ == "FALLING":
        score = min(score*1.09, 100)
    elif "OVER" in t and ht == "RISING" and at_ == "RISING":
        score = min(score*1.09, 100)
    elif "GG" in t and ht == "RISING" and at_ == "RISING":
        score = min(score*1.08, 100)

    # Scale by data confidence: low confidence = can't exceed 65 conviction
    max_conv = 40 + data_conf * 60
    score = min(score, max_conv)

    # Historical calibration
    cal = _calibration()
    if tip in cal and cal[tip]["total"] >= 20:
        cf = max(0.80, min(1.20, cal[tip]["calibration_factor"]))
        score = round(score*cf, 2)

    return min(round(score, 1), 100.0)

# ─────────────────────────────────────────────────────────────────────────────
# REASON BUILDER
# ─────────────────────────────────────────────────────────────────────────────

def _reason(tip, xg_h, xg_a, h_form, a_form, h_stand, a_stand,
            prob, odds, h_name, a_name):
    h  = h_name.split()[0]; a = a_name.split()[0]
    tx = round(xg_h+xg_a, 2)
    hf = form_score(h_form); af = form_score(a_form)
    ht = form_trend(h_form); at_ = form_trend(a_form)
    ev = (f" — bookie underpriced by {value_edge(prob,odds):.1f}%"
          if value_edge(prob,odds) and value_edge(prob,odds)>3 else "")
    t  = tip.upper()

    if "HOME WIN" in t and "EITHER" not in t:
        if xg_h > xg_a*1.25:
            return f"{h} dominating chance creation ({xg_h:.2f} xG vs {xg_a:.2f}) — home superiority unmistakable{ev}"
        if ht == "RISING" and at_ != "RISING":
            return f"{h} in rising form — {a} struggling to match their momentum{ev}"
        if h_stand and a_stand and h_stand < a_stand-4:
            return f"{h} significantly outranks {a} in the table (#{h_stand} vs #{a_stand}){ev}"
        return f"{h} backed by home advantage and marginal edge across xG, form and position{ev}"

    if "AWAY WIN" in t and "EITHER" not in t:
        if xg_a > xg_h*1.25:
            return f"{a} generating more danger on the road ({xg_a:.2f} xG vs {xg_h:.2f}) — quality shining through{ev}"
        if at_ == "RISING" and ht != "RISING":
            return f"{a} flying in form — {h} hosts are inconsistent at home right now{ev}"
        if a_stand and h_stand and a_stand < h_stand-4:
            return f"{a} the superior side in the table (#{a_stand} vs #{h_stand}) — class difference clear{ev}"
        return f"{a} backed by form trajectory and table position despite the away fixture{ev}"

    if "DRAW" in t and "DNB" not in t:
        return f"xG balanced ({xg_h:.2f} vs {xg_a:.2f}) — evenly matched sides, stalemate firmly on cards{ev}"

    if "OVER 3.5" in t: return f"Both sides generating heavily — {tx} combined xG backs an end-to-end thriller{ev}"
    if "OVER 2.5" in t: return f"Combined xG of {tx} signals a multi-goal game — both defences under pressure{ev}"
    if "OVER 1.5" in t: return f"High xG total ({tx}) — at least 2 goals strongly expected in this encounter{ev}"
    if "UNDER 1.5" in t: return f"Very low attacking output — xG {tx}, clean sheet likely from at least one team{ev}"
    if "UNDER 2.5" in t: return f"Limited chance creation ({tx} combined xG) — tight finish backed by the numbers{ev}"
    if t == "GG": return f"Both creating — {h}: {xg_h:.2f} xG · {a}: {xg_a:.2f} xG. Both have the firepower to score{ev}"
    if t == "NG": return f"Low attacking threat — combined xG only {tx}. Clean sheet likely{ev}"
    if "DOUBLE CHANCE 1X" in t: return f"Covering home win and draw — {h} unlikely to lose at home{ev}"
    if "DOUBLE CHANCE X2" in t: return f"Covering draw and away win — {a} unlikely to lose this despite travel{ev}"
    if "DOUBLE CHANCE 12" in t: return f"Covering both wins — draw unlikely given xG gap ({xg_h:.2f} vs {xg_a:.2f}){ev}"
    if "HOME CLEAN SHEET" in t: return f"{a} generating low away xG ({xg_a:.2f}) — {h} defence can shut them out{ev}"
    if "AWAY CLEAN SHEET" in t: return f"{h} creating little at home ({xg_h:.2f} xG) — {a} can keep a clean sheet{ev}"
    if "DNB HOME" in t: return f"{h} backed to win when draw is removed — value without the draw risk{ev}"
    if "DNB AWAY" in t: return f"{a} backed to win when draw is removed — away quality clear on the data{ev}"
    if "EITHER HALF" in t:
        who = h if "HOME" in t else a
        return f"{who} likely to win at least one half — strong enough to assert dominance in one period{ev}"
    if "HT HOME WIN" in t: return f"{h} dominant in early phases — likely to edge the first half{ev}"
    if "HT AWAY WIN" in t: return f"{a} dangerous early — can take the half-time lead{ev}"
    if "HT DRAW" in t: return f"Evenly matched opening expected — HT draw backed by balanced xG{ev}"
    if "OVER" in t: return f"Goals expected — {tx} combined xG supports this market{ev}"
    if "UNDER" in t: return f"Low scoring expected — {tx} combined xG backs the under{ev}"
    return f"{prob:.0f}% probability — multiple signals in agreement{ev}"

# ─────────────────────────────────────────────────────────────────────────────
# MARKET TIER DEFINITIONS
# ─────────────────────────────────────────────────────────────────────────────

# RECOMMENDED: meaningful tips with real discriminating power
_REC = {
    "HOME WIN","AWAY WIN","DRAW",
    "OVER 2.5","OVER 3.5","UNDER 2.5","UNDER 1.5",
    "GG","NG",
    "HOME CLEAN SHEET","AWAY CLEAN SHEET",
    "DNB HOME","DNB AWAY",
    "HOME WIN EITHER HALF","AWAY WIN EITHER HALF",
    "HANDICAP HOME -0.5","HANDICAP AWAY -0.5",
}
_REC_MIN = {   # minimum probability threshold per tip
    "HOME WIN":28, "AWAY WIN":22, "DRAW":22,
    "OVER 2.5":35, "OVER 3.5":15, "UNDER 2.5":20, "UNDER 1.5":8,
    "GG":35, "NG":25,
    "HOME CLEAN SHEET":15, "AWAY CLEAN SHEET":10,
    "DNB HOME":35, "DNB AWAY":28,
    "HOME WIN EITHER HALF":25, "AWAY WIN EITHER HALF":15,
    "HANDICAP HOME -0.5":28, "HANDICAP AWAY -0.5":22,
}
# DNB eligibility: only if the excluded side is weak
_DNB_MAX_OPP = {"DNB HOME":38, "DNB AWAY":38}

# SAFEST: high-prob low-risk options
_SAFE = {
    "OVER 1.5","OVER 0.5",
    "DOUBLE CHANCE 1X","DOUBLE CHANCE X2","DOUBLE CHANCE 12",
    "HOME OVER 0.5","AWAY OVER 0.5",
    "HOME WIN EITHER HALF","AWAY WIN EITHER HALF",
    "HANDICAP HOME +0.5","HANDICAP AWAY +0.5",
}
_SAFE_MIN = 52

# ─────────────────────────────────────────────────────────────────────────────
# TIP PICKERS
# ─────────────────────────────────────────────────────────────────────────────

def _pick_recommended(mkt, xg_h, xg_a, h_form, a_form, h_stand, a_stand,
                      odds_map, data_conf):
    scores = {}
    for tip in _REC:
        prob = mkt.get(tip, 0)
        if prob < _REC_MIN.get(tip, 28): continue
        # DNB: don't recommend if opponent win probability is high
        if tip in _DNB_MAX_OPP:
            opp_key = "AWAY WIN" if "HOME" in tip else "HOME WIN"
            if mkt.get(opp_key, 0) > _DNB_MAX_OPP[tip]: continue
        # Draw: only if genuinely competitive
        if tip == "DRAW" and mkt.get("DRAW",0) < 25: continue
        # UNDER 1.5: only for truly defensive games
        if tip == "UNDER 1.5" and xg_h+xg_a > 2.0: continue
        bk = odds_map.get(tip)
        scores[tip] = conviction(tip, prob, xg_h, xg_a,
                                 h_form, a_form, h_stand, a_stand, bk, data_conf)

    if not scores:  # absolute fallback
        for tip in ("HOME WIN","AWAY WIN","OVER 2.5","GG"):
            scores[tip] = conviction(tip, mkt.get(tip,40), xg_h, xg_a,
                                     h_form, a_form, h_stand, a_stand,
                                     data_conf=data_conf)

    best = max(scores, key=scores.get)
    return best, round(mkt.get(best,0),1), round(scores[best],1), scores

def _pick_safest(rec_tip, mkt, xg_h, xg_a, h_form, a_form, h_stand, a_stand,
                 data_conf):
    scored = []
    for tip in _SAFE:
        if tip == rec_tip: continue
        prob = mkt.get(tip, 0)
        if prob < _SAFE_MIN: continue
        sc = conviction(tip, prob, xg_h, xg_a, h_form, a_form,
                        h_stand, a_stand, data_conf=data_conf)
        scored.append((tip, prob, sc))
    if not scored:
        for tip in ("DOUBLE CHANCE 12","OVER 1.5","HOME OVER 0.5"):
            scored.append((tip, mkt.get(tip,72), 30.0))
    scored.sort(key=lambda x: x[2], reverse=True)
    b = scored[0]
    return b[0], round(b[1],1), round(100/max(b[1],1),2)

def _pick_risky(rec_tip, mkt, xg_h, xg_a, hw, dw, aw, o25, btts):
    combos = []

    # DRAW — only genuinely competitive
    dp = mkt.get("DRAW", dw)
    if dp >= 26 and (max(hw,aw)-dp) <= 18:
        combos.append({"tip":"DRAW","prob":round(dp,1),
                       "odds":round(100/max(dp,1),2)})

    # Outcome combos
    fav = "HOME" if hw >= aw else "AWAY"; fp = max(hw,aw)
    combos += [
        {"tip":f"{fav} WIN & GG",
         "prob":round(fp/100*btts/100*100,1),
         "odds":round((100/max(fp,1))*(100/max(btts,1))/100,2)},
        {"tip":f"{fav} WIN & OVER 2.5",
         "prob":round(fp/100*o25/100*100,1),
         "odds":round((100/max(fp,1))*(100/max(o25,1))/100,2)},
        {"tip":f"HT/FT: {fav} / {fav}",
         "prob":round(fp*0.52,1),
         "odds":round(100/max(fp*0.52,1),2)},
        {"tip":"GG & OVER 2.5",
         "prob":round(btts/100*o25/100*100,1),
         "odds":round((100/max(btts,1))*(100/max(o25,1))/100,2)},
    ]

    # HT specials
    for htip in ("HT HOME WIN","HT AWAY WIN","HT OVER 1.5"):
        p = mkt.get(htip,0)
        if p >= 20:
            combos.append({"tip":htip,"prob":round(p,1),
                           "odds":round(100/max(p,1),2)})

    # Odd/Even
    op = mkt.get("ODD GOALS",0); ep = mkt.get("EVEN GOALS",0)
    best_oe = ("ODD GOALS",op) if op>ep else ("EVEN GOALS",ep)
    if best_oe[1] >= 48:
        combos.append({"tip":best_oe[0],"prob":round(best_oe[1],1),
                       "odds":round(100/max(best_oe[1],1),2)})

    # Team specials
    for tp in ("HOME OVER 1.5","AWAY OVER 0.5","AWAY CLEAN SHEET","HOME CLEAN SHEET"):
        p = mkt.get(tp,0)
        if 25 <= p <= 62:  # avoid trivial or impossible picks
            combos.append({"tip":tp,"prob":round(p,1),
                           "odds":round(100/max(p,1),2)})

    combos = [c for c in combos if c["tip"] != rec_tip and c["prob"] >= 10]
    combos.sort(key=lambda x: x["prob"], reverse=True)
    # Remove duplicates by tip name
    seen = set(); unique = []
    for c in combos:
        if c["tip"] not in seen: seen.add(c["tip"]); unique.append(c)

    if not unique:
        unique = [{"tip":"GG & OVER 1.5",
                   "prob":round(btts*0.82,1),
                   "odds":round(100/max(btts*0.82,1),2)}]
    return unique[:5]

# ─────────────────────────────────────────────────────────────────────────────
# SMART TAGGING
# ─────────────────────────────────────────────────────────────────────────────

def smart_tag(rec_tip, rec_conv, rec_prob, hw, dw, aw, h_form, a_form,
              h_inj, a_inj, h_stand, a_stand, xg_h, xg_a,
              lg_name="", data_conf=0.5):
    """
    Intelligent tag based on all available signals.
    data_conf heavily influences the maximum tag achievable.
    """
    hfc = [r for r in (h_form or []) if r.upper() in ("W","D","L")]
    afc = [r for r in (a_form or []) if r.upper() in ("W","D","L")]
    h_hot   = len(hfc)>=3 and hfc[-3:].count("W")>=3
    a_hot   = len(afc)>=3 and afc[-3:].count("W")>=3
    h_slump = len(hfc)>=3 and hfc[-3:].count("L")>=3
    a_slump = len(afc)>=3 and afc[-3:].count("L")>=3
    ht = form_trend(hfc); at_ = form_trend(afc)
    inj     = len(h_inj or []) + len(a_inj or [])
    fav     = max(hw, aw)
    ll      = (lg_name or "").lower()
    is_cup  = any(w in ll for w in ["cup","copa","carabao","pokal","coupe","coppa"])
    is_friendly = "friendly" in ll

    # Signal agreement count
    agree = 0
    if h_stand and a_stand:
        if "HOME" in rec_tip and h_stand < a_stand: agree+=1
        if "AWAY" in rec_tip and a_stand < h_stand: agree+=1
    if "HOME" in rec_tip and xg_h > xg_a: agree+=1
    if "AWAY" in rec_tip and xg_a > xg_h: agree+=1
    if "HOME" in rec_tip and (h_hot or ht=="RISING"): agree+=1
    if "AWAY" in rec_tip and (a_hot or at_=="RISING"): agree+=1
    if "OVER" in rec_tip and xg_h+xg_a > 2.3: agree+=1
    if "UNDER" in rec_tip and xg_h+xg_a < 1.8: agree+=1
    if "GG" == rec_tip and xg_h>0.8 and xg_a>0.8: agree+=1

    # Priority order
    if is_friendly: return "VOLATILE", "volatile"
    if is_cup and fav < 55: return "VOLATILE", "volatile"

    # AVOID — slump or 3-way toss-up
    if (h_slump and "HOME" in rec_tip) or (a_slump and "AWAY" in rec_tip):
        return "AVOID", "avoid"
    if abs(hw-dw)<5 and abs(dw-aw)<5 and fav < 44 and data_conf < 0.5:
        return "AVOID", "avoid"
    if inj >= 6 and rec_conv < 46:
        return "AVOID", "avoid"

    # Data-gated tags — can't claim SURE/RELIABLE without real data
    if data_conf >= 0.6:
        if fav>=72 and rec_conv>=62 and agree>=3 and inj==0 and not h_slump and not a_slump:
            return "SURE MATCH", "sure"
        if rec_conv>=56 and rec_prob>=52 and agree>=2:
            return "RELIABLE", "reliable"

    if rec_conv >= 44:
        return "SOLID", "solid"

    return "MONITOR", "monitor"

# ─────────────────────────────────────────────────────────────────────────────
# MAIN PUBLIC INTERFACE
# ─────────────────────────────────────────────────────────────────────────────

def full_prediction(h_name, a_name,
                    base_xg_h=1.35, base_xg_a=1.05,
                    h_form=None, a_form=None,
                    h_stand=None, a_stand=None,
                    h2h=None, h_inj=None, a_inj=None,
                    odds_h=None, odds_d=None, odds_a=None,
                    odds_o25=None, odds_o15=None, odds_btts=None,
                    lg_name="", h_profile=None, a_profile=None,
                    h_luck=0.0, a_luck=0.0,
                    # Override probabilities from external source (Sportmonks etc.)
                    ext_hw=0, ext_dw=0, ext_aw=0, ext_o25=0, ext_btts=0):
    """
    GOD MODE: full intelligence pipeline → full market → best 3 tips.
    """
    try:
        h_form = h_form or []; a_form = a_form or []
        h_inj  = h_inj  or []; a_inj  = a_inj  or []

        # Step 1: Calibrate xG
        xg_h, xg_a, data_conf = calibrate_xg(
            base_xg_h, base_xg_a, h_form, a_form, h_stand, a_stand,
            h_profile, a_profile, h_luck, a_luck)

        # Step 2: Full market matrix from Poisson
        mkt = _full_market_matrix(xg_h, xg_a)

        # Step 3: Blend with external probs if available (Sportmonks/Bzzoiro)
        if ext_hw > 0 and ext_dw > 0 and ext_aw > 0:
            blend = min(0.45, data_conf * 0.5)  # trust external more when we have less data
            ext_blend = 1 - blend
            mkt["HOME WIN"] = round(mkt["HOME WIN"]*blend + ext_hw*ext_blend, 1)
            mkt["DRAW"]     = round(mkt["DRAW"]    *blend + ext_dw*ext_blend, 1)
            mkt["AWAY WIN"] = round(mkt["AWAY WIN"]*blend + ext_aw*ext_blend, 1)
            if ext_o25 > 0:
                mkt["OVER 2.5"]  = round(mkt["OVER 2.5"] *blend + ext_o25 *ext_blend, 1)
                mkt["UNDER 2.5"] = round(100 - mkt["OVER 2.5"], 1)
            if ext_btts > 0:
                mkt["GG"] = round(mkt["GG"]*blend + ext_btts*ext_blend, 1)
                mkt["NG"] = round(100-mkt["GG"], 1)
            # Renormalise 1X2
            tot = mkt["HOME WIN"]+mkt["DRAW"]+mkt["AWAY WIN"]
            if tot > 0 and abs(tot-100) > 1:
                mkt["HOME WIN"] = round(mkt["HOME WIN"]/tot*100,1)
                mkt["DRAW"]     = round(mkt["DRAW"]    /tot*100,1)
                mkt["AWAY WIN"] = round(mkt["AWAY WIN"]/tot*100,1)

        hw = mkt["HOME WIN"]; dw = mkt["DRAW"]; aw = mkt["AWAY WIN"]
        o25 = mkt["OVER 2.5"]; btts = mkt["GG"]

        odds_map = {}
        if odds_h:   odds_map["HOME WIN"] = odds_h
        if odds_d:   odds_map["DRAW"]     = odds_d
        if odds_a:   odds_map["AWAY WIN"] = odds_a
        if odds_o25: odds_map["OVER 2.5"] = odds_o25
        if odds_o15: odds_map["OVER 1.5"] = odds_o15
        if odds_btts:odds_map["GG"]       = odds_btts

        # Step 4: Pick tips
        rec_tip, rec_prob, rec_conv, all_scores = _pick_recommended(
            mkt, xg_h, xg_a, h_form, a_form, h_stand, a_stand,
            odds_map, data_conf)

        safe_tip, safe_prob, safe_fair = _pick_safest(
            rec_tip, mkt, xg_h, xg_a, h_form, a_form, h_stand, a_stand, data_conf)

        risky_list = _pick_risky(rec_tip, mkt, xg_h, xg_a, hw, dw, aw, o25, btts)

        # Step 5: Reason
        reason = _reason(rec_tip, xg_h, xg_a, h_form, a_form, h_stand, a_stand,
                         rec_prob, odds_map.get(rec_tip), h_name, a_name)

        fair_odds = round(100/max(rec_prob,1), 2)
        edge_val  = value_edge(rec_prob, odds_map.get(rec_tip))

        # Step 6: Tag
        tag, tc = smart_tag(rec_tip, rec_conv, rec_prob, hw, dw, aw,
                             h_form, a_form, h_inj, a_inj, h_stand, a_stand,
                             xg_h, xg_a, lg_name, data_conf)

        return {
            "tag": tag, "tc": tc,
            "xg_h": round(xg_h,2), "xg_a": round(xg_a,2),
            "data_conf": round(data_conf,2),
            "markets": mkt,
            "1x2": {"home":hw, "draw":dw, "away":aw},
            "recommended": {
                "tip": rec_tip, "prob": rec_prob, "conv": rec_conv,
                "fair": fair_odds, "edge": edge_val, "reason": reason,
            },
            "safest": {"tip": safe_tip, "prob": safe_prob, "fair": safe_fair},
            "risky":  risky_list,
            "momentum": momentum_score(h_form, a_form, xg_h, xg_a),
            "style":    style_profile(xg_h, xg_a, btts),
        }
    except Exception as e:
        import traceback; traceback.print_exc()
        return None

# ─────────────────────────────────────────────────────────────────────────────
# LEGACY WRAPPERS  (called by existing app.py and scheduler.py)
# ─────────────────────────────────────────────────────────────────────────────

def _pick_recommended(h_win, draw, a_win, o15, o25, o35, btts, gg_p, ng_p,
                      xg_h, xg_a, h_form, a_form, h_stand, a_stand,
                      odds_h, odds_d, odds_a, odds_o15, odds_o25, odds_btts):
    mkt = _full_market_matrix(xg_h, xg_a)
    mkt.update({"HOME WIN":h_win,"DRAW":draw,"AWAY WIN":a_win,
                "OVER 1.5":o15,"OVER 2.5":o25,"OVER 3.5":o35,
                "GG":gg_p,"NG":ng_p})
    odds_map = {k:v for k,v in [("HOME WIN",odds_h),("DRAW",odds_d),
                ("AWAY WIN",odds_a),("OVER 1.5",odds_o15),
                ("OVER 2.5",odds_o25),("GG",odds_btts)] if v}
    tip, prob, conv, scores = _pick_rec_inner(mkt, xg_h, xg_a, h_form, a_form,
                                               h_stand, a_stand, odds_map, 0.5)
    return tip, prob, conv, odds_map.get(tip), scores

def _pick_rec_inner(mkt, xg_h, xg_a, h_form, a_form, h_stand, a_stand,
                    odds_map, dc):
    scores = {}
    for tip in _REC:
        prob = mkt.get(tip,0)
        if prob < _REC_MIN.get(tip,28): continue
        if tip=="DRAW" and prob<25: continue
        bk = odds_map.get(tip)
        scores[tip] = conviction(tip, prob, xg_h, xg_a, h_form, a_form,
                                 h_stand, a_stand, bk, dc)
    if not scores:
        for tip in ("HOME WIN","AWAY WIN","OVER 2.5","GG"):
            scores[tip] = conviction(tip, mkt.get(tip,40), xg_h, xg_a,
                                     h_form, a_form, h_stand, a_stand, data_conf=dc)
    best = max(scores, key=scores.get)
    return best, round(mkt.get(best,0),1), round(scores[best],1), scores

def _pick_safest(rec_tip, h_win, draw, a_win, o15, xg_h, xg_a,
                 h_form, a_form, odds_h, odds_d, odds_a):
    mkt = _full_market_matrix(xg_h, xg_a)
    mkt.update({"HOME WIN":h_win,"DRAW":draw,"AWAY WIN":a_win,"OVER 1.5":o15})
    return _pick_safest_inner(rec_tip, mkt, xg_h, xg_a, h_form, a_form, None, None, 0.5)

def _pick_safest_inner(rec_tip, mkt, xg_h, xg_a, h_form, a_form,
                       h_stand, a_stand, dc):
    scored = []
    for tip in _SAFE:
        if tip==rec_tip: continue
        prob = mkt.get(tip,0)
        if prob < _SAFE_MIN: continue
        sc = conviction(tip, prob, xg_h, xg_a, h_form, a_form,
                        h_stand or 10, a_stand or 10, data_conf=dc)
        scored.append((tip, prob, sc))
    if not scored:
        for tip in ("DOUBLE CHANCE 12","OVER 1.5","HOME OVER 0.5"):
            scored.append((tip, mkt.get(tip,72), 30.0))
    scored.sort(key=lambda x: x[2], reverse=True)
    b = scored[0]
    return b[0], round(b[1],1), round(100/max(b[1],1),2)

def _pick_risky(h_win, draw, a_win, o15, o25, btts, xg_h, xg_a,
                h_form, a_form, odds_h, odds_a, odds_o25, odds_btts):
    mkt = _full_market_matrix(xg_h, xg_a)
    mkt.update({"HOME WIN":h_win,"DRAW":draw,"AWAY WIN":a_win,
                "OVER 2.5":o25,"GG":btts})
    return _pick_risky(rec_tip="", mkt=mkt, xg_h=xg_h, xg_a=xg_a,
                       hw=h_win, dw=draw, aw=a_win, o25=o25, btts=btts) \
        if False else _pick_risky_core("", mkt, xg_h, xg_a, h_win, draw, a_win, o25, btts)

def _pick_risky_core(rec_tip, mkt, xg_h, xg_a, hw, dw, aw, o25, btts):
    return _pick_risky.__wrapped__(rec_tip, mkt, xg_h, xg_a, hw, dw, aw, o25, btts) \
        if hasattr(_pick_risky,"__wrapped__") else \
        _pick_risky_impl(rec_tip, mkt, xg_h, xg_a, hw, dw, aw, o25, btts)

def _pick_risky_impl(rec_tip, mkt, xg_h, xg_a, hw, dw, aw, o25, btts):
    # Alias the module-level risky picker
    import sys
    me = sys.modules[__name__]
    return me._risky_impl(rec_tip, mkt, hw, dw, aw, o25, btts)

def _risky_impl(rec_tip, mkt, hw, dw, aw, o25, btts):
    combos = []
    dp = mkt.get("DRAW",dw)
    if dp>=26 and (max(hw,aw)-dp)<=18:
        combos.append({"tip":"DRAW","prob":round(dp,1),"odds":round(100/max(dp,1),2)})
    fav = "HOME" if hw>=aw else "AWAY"; fp = max(hw,aw)
    combos += [
        {"tip":f"{fav} WIN & GG","prob":round(fp/100*btts/100*100,1),
         "odds":round((100/max(fp,1))*(100/max(btts,1))/100,2)},
        {"tip":f"{fav} WIN & OVER 2.5","prob":round(fp/100*o25/100*100,1),
         "odds":round((100/max(fp,1))*(100/max(o25,1))/100,2)},
        {"tip":f"HT/FT: {fav} / {fav}","prob":round(fp*0.52,1),
         "odds":round(100/max(fp*0.52,1),2)},
        {"tip":"GG & OVER 2.5","prob":round(btts/100*o25/100*100,1),
         "odds":round((100/max(btts,1))*(100/max(o25,1))/100,2)},
    ]
    for ht in ("HT HOME WIN","HT AWAY WIN","HT OVER 1.5"):
        p = mkt.get(ht,0)
        if p>=20: combos.append({"tip":ht,"prob":round(p,1),"odds":round(100/max(p,1),2)})
    op=mkt.get("ODD GOALS",0); ep=mkt.get("EVEN GOALS",0)
    boe=("ODD GOALS",op) if op>ep else ("EVEN GOALS",ep)
    if boe[1]>=48: combos.append({"tip":boe[0],"prob":round(boe[1],1),"odds":round(100/max(boe[1],1),2)})
    combos=[c for c in combos if c["tip"]!=rec_tip and c["prob"]>=10]
    combos.sort(key=lambda x:x["prob"],reverse=True)
    seen=set(); unique=[]
    for c in combos:
        if c["tip"] not in seen: seen.add(c["tip"]); unique.append(c)
    if not unique:
        unique=[{"tip":"GG & OVER 1.5","prob":round(btts*0.82,1),
                 "odds":round(100/max(btts*0.82,1),2)}]
    return unique[:5]

# expose legacy names
_self = sys.modules[__name__]
_self.form_score      = form_score
_self.form_trend      = form_trend
_self.momentum_score  = momentum_score
_self.style_profile   = style_profile
_self.value_edge      = value_edge
_self.smart_tag       = smart_tag
_self._smart_tag      = smart_tag
_self._risky_impl     = _risky_impl
_self.analyze_match   = lambda *a,**k: None   # unused
