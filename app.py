from flask import Flask, render_template_string, request, jsonify, Response
import os, math, json, requests
from datetime import datetime, timedelta, timezone
import match_predictor, database, sportmonks, scheduler

app = Flask(__name__)
database.init_db()

WAT = 1  # UTC+1 Nigeria

# ─────────────────────────────────────────────────────────────
# TIME HELPERS
# ─────────────────────────────────────────────────────────────

def now_wat():
    return datetime.now(timezone.utc) + timedelta(hours=WAT)

def parse_kickoff(raw):
    if not raw: return now_wat()
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z","+00:00"))
        if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
        return dt + timedelta(hours=WAT)
    except:
        return now_wat()

def kickoff_label(raw):
    dt = parse_kickoff(raw)
    today = now_wat().date()
    if dt.date() == today: return dt.strftime("%H:%M")
    return dt.strftime("%H:%M %d %b")

# ─────────────────────────────────────────────────────────────
# LEAGUE METADATA
# ─────────────────────────────────────────────────────────────

LEAGUE_META = {
    "Premier League":         {"icon":"🏴󠁧󠁢󠁥󠁮󠁧󠁿","country":"England","tier":1},
    "La Liga":                {"icon":"🇪🇸","country":"Spain","tier":1},
    "Serie A":                {"icon":"🇮🇹","country":"Italy","tier":1},
    "Bundesliga":             {"icon":"🇩🇪","country":"Germany","tier":1},
    "Ligue 1":                {"icon":"🇫🇷","country":"France","tier":1},
    "UEFA Champions League":  {"icon":"🏆","country":"Europe","tier":1},
    "UEFA Europa League":     {"icon":"🏆","country":"Europe","tier":1},
    "UEFA Conference League": {"icon":"🏆","country":"Europe","tier":2},
    "Championship":           {"icon":"🏴󠁧󠁢󠁥󠁮󠁧󠁿","country":"England","tier":2},
    "Eredivisie":             {"icon":"🇳🇱","country":"Netherlands","tier":2},
    "Primeira Liga":          {"icon":"🇵🇹","country":"Portugal","tier":2},
    "Super Lig":              {"icon":"🇹🇷","country":"Turkey","tier":2},
    "Scottish Premiership":   {"icon":"🏴󠁧󠁢󠁳󠁣󠁴󠁿","country":"Scotland","tier":2},
    "Belgian Pro League":     {"icon":"🇧🇪","country":"Belgium","tier":2},
    "Jupiler Pro League":     {"icon":"🇧🇪","country":"Belgium","tier":2},
    "MLS":                    {"icon":"🇺🇸","country":"USA","tier":2},
    "Liga MX":                {"icon":"🇲🇽","country":"Mexico","tier":2},
    "Brasileirao":            {"icon":"🇧🇷","country":"Brazil","tier":2},
    "Saudi Professional League":{"icon":"🇸🇦","country":"Saudi Arabia","tier":2},
    "Eliteserien":            {"icon":"🇳🇴","country":"Norway","tier":3},
    "Allsvenskan":            {"icon":"🇸🇪","country":"Sweden","tier":3},
    "Ekstraklasa":            {"icon":"🇵🇱","country":"Poland","tier":3},
    "Czech Liga":             {"icon":"🇨🇿","country":"Czech Rep","tier":3},
    "Greek Super League":     {"icon":"🇬🇷","country":"Greece","tier":3},
    "J1 League":              {"icon":"🇯🇵","country":"Japan","tier":3},
    "Chinese Super League":   {"icon":"🇨🇳","country":"China","tier":3},
    "NPFL":                   {"icon":"🇳🇬","country":"Nigeria","tier":2},
    "CAF Champions League":   {"icon":"🏆","country":"Africa","tier":2},
}

def get_league_meta(name):
    if not name: return {"icon":"🌐","country":"World","tier":3}
    n = name.strip()
    if n in LEAGUE_META: return LEAGUE_META[n]
    nl = n.lower()
    for k, v in LEAGUE_META.items():
        if k.lower() in nl or nl in k.lower(): return v
    return {"icon":"🌐","country":"World","tier":3}

# ─────────────────────────────────────────────────────────────
# FIXTURE PARSING
# ─────────────────────────────────────────────────────────────

def build_fixture_card(fx):
    """Convert Sportmonks fixture into our standard card format."""
    h_id, h_name, a_id, a_name = sportmonks.extract_teams(fx)
    state  = sportmonks.extract_state(fx)
    h_g, a_g = sportmonks.extract_score(fx)
    league = fx.get("league") or {}
    l_name = league.get("name","") if isinstance(league, dict) else ""
    l_id   = league.get("id",0) if isinstance(league, dict) else 0
    l_country_raw = ""
    if isinstance(league, dict):
        c_obj = league.get("country") or {}
        if isinstance(c_obj, dict): l_country_raw = c_obj.get("name","")
    meta = get_league_meta(l_name)
    if l_country_raw: meta = dict(meta); meta["country"] = l_country_raw
    raw_ko = fx.get("starting_at") or fx.get("date","")

    live_states = {"1H","2H","HT","ET","PEN","LIVE","INPLAY"}
    is_live = state.upper() in live_states or state.isdigit()
    is_ft   = state.upper() in ("FT","AET","PEN","FIN","FINISHED","AWARDED")
    is_ns   = not is_live and not is_ft

    ko_dt = parse_kickoff(raw_ko)
    _today = now_wat().date(); _tmrw = _today + timedelta(days=1)
    if ko_dt.date() == _today:  date_label = "TODAY"
    elif ko_dt.date() == _tmrw: date_label = "TOMORROW"
    else:                       date_label = ko_dt.strftime("%a %-d %b").upper()
    return {
        "id":         fx.get("id"),
        "home_id":    h_id, "home": h_name or "Home",
        "away_id":    a_id, "away": a_name or "Away",
        "league":     l_name, "league_id": l_id,
        "country":    meta["country"], "icon": meta["icon"], "tier": meta["tier"],
        "kickoff":    raw_ko,
        "date_label": date_label,
        "state":      state,
        "is_live":    is_live,
        "is_ft":      is_ft,
        "is_ns":      is_ns,
        "score_h":    h_g, "score_a": a_g,
    }

def get_all_cards(days=3):
    """Get fixtures for next N days as standard cards."""
    ck = f"window_cards_v2_{days}"
    cached = database.cache_get("h2h_cache", ck, max_age_hours=0.4)
    if cached:
        try: return json.loads(cached)
        except: pass
    fixtures = sportmonks.get_fixtures_window(days)
    cards = [build_fixture_card(f) for f in fixtures]
    cards.sort(key=lambda c: c["kickoff"] or "")
    database.cache_set("h2h_cache", ck, json.dumps(cards))
    return cards

def get_all_today_cards():
    return get_all_cards(3)

# ─────────────────────────────────────────────────────────────
# QUICK PREDICTION (for list views -- no API calls)
# ─────────────────────────────────────────────────────────────

def quick_predict(card, preds=None):
    if not preds: return "--", 0, "MONITOR"
    hw = preds.get("home_win", 33.3)
    dw = preds.get("draw", 33.3)
    aw = preds.get("away_win", 33.3)
    o25 = preds.get("over_25", 45)
    btts = preds.get("btts", 45)

    best_tip = max([
        ("HOME WIN", hw),
        ("DRAW", dw),
        ("AWAY WIN", aw),
        ("OVER 2.5", o25),
        ("GG", btts),
    ], key=lambda x: x[1])

    tip, prob = best_tip
    if prob >= 70 and tip != "DRAW":
        tag = "RELIABLE"
    elif prob >= 58:
        tag = "SOLID"
    else:
        tag = "MONITOR"
    return tip, round(prob, 1), tag

# ─────────────────────────────────────────────────────────────
# UI HELPERS
# ─────────────────────────────────────────────────────────────

def tip_color(tip):
    if "WIN" in tip:     return "var(--g)"
    if "OVER" in tip:    return "var(--b)"
    if "GG" in tip:      return "var(--cy)"
    if "UNDER" in tip:   return "var(--gold)"
    if "DRAW" in tip:    return "var(--w)"
    return "var(--t2)"

def form_dot(r):
    cls = {"W":"w","D":"d","L":"l"}.get(r.upper(),"d")
    return f'<span class="fd fd-{cls}">{r.upper()}</span>'

def form_dots(fl):
    if not fl: return '<span class="no-data">--</span>'
    return "".join(form_dot(r) for r in list(fl)[-5:])

def prob_bar(label, pct, color="green", icon=""):
    c = {"green":"var(--g)","blue":"var(--b)","orange":"var(--w)","red":"var(--r)","cyan":"var(--cy)"}.get(color,"var(--g)")
    pct = min(round(float(pct),1), 100)
    return f'''<div class="pb-row">
      <div class="pb-top"><span class="pb-label">{icon} {label}</span><span class="pb-val" style="color:{c}">{pct}%</span></div>
      <div class="pb-track"><div class="pb-fill" style="width:{pct}%;background:{c}"></div></div>
    </div>'''

def live_dot():
    return '<span class="live-pulse"></span>'

def state_badge(card):
    if card["is_live"]:
        s = card["state"]
        min_str = f"{s}'" if str(s).isdigit() else s
        return f'<span class="s-badge s-live">{live_dot()} {min_str}</span>'
    if card["is_ft"]:
        return '<span class="s-badge s-ft">FT</span>'
    return f'<span class="s-badge s-ns">{kickoff_label(card["kickoff"])}</span>'

def score_display(card):
    if card["score_h"] is not None and card["score_a"] is not None:
        return f'<span class="score">{card["score_h"]} - {card["score_a"]}</span>'
    return ""

# ─────────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────────

CSS = """
:root{
  --bg:#03050a;--s:#080c14;--s2:#0d1220;--s3:#131929;--s4:#1a2235;
  --g:#00ff87;--g2:#00e676;--b:#4f8ef7;--b2:#3b7cf0;
  --w:#ff9f0a;--r:#ff453a;--pu:#bf5af2;--cy:#32d7f0;--gold:#ffd60a;
  --t:#4a5568;--t2:#718096;--t3:#94a3b8;--wh:#f0f4f8;
  --bdr:rgba(255,255,255,.04);--bdr2:rgba(255,255,255,.08);--bdr3:rgba(255,255,255,.13);
  --glow:0 0 40px rgba(0,255,135,.06);
  --card-bg:linear-gradient(145deg,#0a0f1a,#080c14);
  --green-glow:0 0 20px rgba(0,255,135,.15);
}
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
html{scroll-behavior:smooth;height:100%}
body{background:var(--bg);color:var(--t3);font-family:-apple-system,BlinkMacSystemFont,'SF Pro Display','Inter',sans-serif;font-size:13px;min-height:100vh;padding-bottom:90px;overflow-x:hidden}
a{text-decoration:none;color:inherit}
::selection{background:rgba(0,255,135,.15)}
::-webkit-scrollbar{width:2px;height:2px}
::-webkit-scrollbar-thumb{background:var(--bdr3);border-radius:2px}

nav{position:sticky;top:0;z-index:300;background:rgba(3,5,10,.88);backdrop-filter:blur(32px) saturate(180%);-webkit-backdrop-filter:blur(32px) saturate(180%);border-bottom:1px solid var(--bdr)}
.nav-inner{max-width:520px;margin:0 auto;display:flex;justify-content:space-between;align-items:center;padding:13px 16px}
.logo{display:flex;align-items:baseline;gap:1px}
.logo-pro{font-size:1.05rem;font-weight:900;color:var(--wh);letter-spacing:-.5px}
.logo-pred{font-size:1.05rem;font-weight:900;color:var(--g);letter-spacing:-.5px}
.logo-ng{font-size:.48rem;font-weight:600;letter-spacing:2px;color:var(--t2);text-transform:uppercase;margin-left:3px;margin-bottom:1px}
.nav-right{display:flex;align-items:center;gap:6px}
.npill{font-size:.56rem;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;padding:5px 11px;border-radius:50px;border:1px solid var(--bdr2);color:var(--t2);transition:all .18s;white-space:nowrap}
.npill:active,.npill.on{border-color:var(--g);color:var(--g);background:rgba(0,255,135,.07)}
.live-count{font-size:.5rem;font-weight:800;padding:3px 7px;border-radius:50px;background:rgba(255,69,58,.15);color:var(--r);border:1px solid rgba(255,69,58,.25);letter-spacing:.5px}

.shell{max-width:520px;margin:0 auto;padding:0 14px}

.hero{padding:22px 0 16px;position:relative}
.hero-eyebrow{font-size:.52rem;font-weight:600;letter-spacing:3px;text-transform:uppercase;color:var(--t2);margin-bottom:8px}
.hero-title{font-size:2.8rem;font-weight:900;color:var(--wh);line-height:.95;letter-spacing:-1.5px;margin-bottom:6px}
.hero-title span{color:var(--g)}
.hero-sub{font-size:.65rem;color:var(--t2);letter-spacing:.3px}
.hero-stats{display:flex;gap:16px;margin-top:14px}
.hstat{display:flex;flex-direction:column;gap:2px}
.hstat-n{font-size:1.6rem;font-weight:900;color:var(--wh);letter-spacing:-1px;line-height:1}
.hstat-l{font-size:.5rem;font-weight:600;letter-spacing:1.8px;text-transform:uppercase;color:var(--t2)}

.search-wrap{position:relative;margin-bottom:14px}
.search-inp{width:100%;background:var(--s2);border:1px solid var(--bdr2);border-radius:14px;padding:11px 14px 11px 40px;color:var(--wh);font-size:.78rem;outline:none;transition:all .2s;-webkit-appearance:none}
.search-inp:focus{border-color:rgba(0,255,135,.35);background:var(--s3);box-shadow:0 0 0 3px rgba(0,255,135,.06)}
.search-inp::placeholder{color:var(--t)}
.s-icon{position:absolute;left:13px;top:50%;transform:translateY(-50%);color:var(--t);pointer-events:none;font-size:.85rem}
.s-clear{position:absolute;right:12px;top:50%;transform:translateY(-50%);color:var(--t);cursor:pointer;display:none;font-size:.72rem;padding:4px;background:var(--s3);border-radius:50%;width:20px;height:20px;align-items:center;justify-content:center}
.s-clear.vis{display:flex}

.sec-hd{font-size:.52rem;font-weight:700;letter-spacing:2.5px;text-transform:uppercase;color:var(--t2);padding:18px 0 10px;display:flex;align-items:center;gap:10px}
.sec-hd::after{content:'';flex:1;height:1px;background:var(--bdr)}
.sec-hd-dot{width:5px;height:5px;border-radius:50%;background:var(--g);flex-shrink:0}

.lg-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:6px}
.lg-tile{background:var(--card-bg);border:1px solid var(--bdr);border-radius:16px;padding:15px 13px;cursor:pointer;transition:all .2s;position:relative;overflow:hidden;display:block}
.lg-tile::before{content:'';position:absolute;inset:0;background:linear-gradient(135deg,rgba(0,255,135,.03),transparent);opacity:0;transition:opacity .2s;border-radius:16px}
.lg-tile:active,.lg-tile:hover{border-color:rgba(0,255,135,.2);transform:scale(.975);box-shadow:var(--green-glow)}
.lg-tile:active::before,.lg-tile:hover::before{opacity:1}
.lg-tile.dim{opacity:.3;pointer-events:none}
.lt-icon{font-size:1.5rem;margin-bottom:7px;display:block}
.lt-name{font-size:.73rem;font-weight:800;color:var(--wh);line-height:1.2;margin-bottom:3px}
.lt-country{font-size:.54rem;letter-spacing:1.2px;text-transform:uppercase;color:var(--t2)}
.lt-fixtures{position:absolute;top:10px;right:10px;font-size:.52rem;font-weight:700;color:var(--g);background:rgba(0,255,135,.1);border:1px solid rgba(0,255,135,.15);border-radius:50px;padding:2px 7px;letter-spacing:.5px}

.fx-wrap{border-radius:18px;overflow:hidden;border:1px solid var(--bdr);background:var(--s)}
.fx-row{display:flex;align-items:center;padding:13px 14px;border-bottom:1px solid var(--bdr);cursor:pointer;transition:background .15s;gap:10px;text-decoration:none;color:inherit}
.fx-row:last-child{border-bottom:none}
.fx-row:active,.fx-row:hover{background:rgba(255,255,255,.025)}
.fx-time{flex-shrink:0;width:42px;text-align:center}
.fx-teams{flex:1;min-width:0}
.fx-home{font-size:.74rem;font-weight:700;color:var(--wh);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-bottom:2px}
.fx-away{font-size:.7rem;color:var(--t3);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.fx-right{flex-shrink:0;text-align:right;display:flex;flex-direction:column;align-items:flex-end;gap:3px}
.fx-tip{font-size:.62rem;font-weight:800;letter-spacing:.8px}
.fx-prob{font-size:.58rem;color:var(--t2);font-weight:600}
.fx-tag{font-size:.52rem;font-weight:700;letter-spacing:.8px}

.s-badge{display:inline-flex;align-items:center;gap:3px;font-size:.56rem;font-weight:700;letter-spacing:.8px;padding:3px 7px;border-radius:50px}
.s-live{background:rgba(255,69,58,.12);color:var(--r);border:1px solid rgba(255,69,58,.25)}
.s-ft{background:rgba(74,85,104,.15);color:var(--t2);border:1px solid var(--bdr2)}
.s-ns{background:transparent;color:var(--t2);font-size:.62rem;border:none;padding:0}
.score{font-size:.9rem;font-weight:900;color:var(--wh);letter-spacing:-0.5px}

.live-pulse{display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--r);animation:pulse 1.4s ease-in-out infinite;flex-shrink:0}
@keyframes pulse{0%,100%{opacity:1;box-shadow:0 0 0 0 rgba(255,69,58,.4)}50%{opacity:.7;box-shadow:0 0 0 4px rgba(255,69,58,0)}}

.tabs{display:flex;gap:5px;overflow-x:auto;padding:2px 0 10px;scrollbar-width:none;margin-bottom:2px}
.tabs::-webkit-scrollbar{display:none}
.tab{flex-shrink:0;font-size:.58rem;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;padding:6px 13px;border-radius:50px;border:1px solid var(--bdr2);color:var(--t2);white-space:nowrap;transition:all .18s;cursor:pointer;display:flex;align-items:center;gap:5px}
.tab.on,.tab:active{border-color:var(--g);color:var(--g);background:rgba(0,255,135,.07)}
.tab-n{font-size:.52rem;background:rgba(0,255,135,.12);color:var(--g);border-radius:50px;padding:1px 5px;font-weight:800}

.match-hero{background:linear-gradient(180deg,rgba(0,255,135,.06) 0%,transparent 100%);border:1px solid rgba(0,255,135,.1);border-radius:20px;padding:22px 18px;margin-bottom:10px;text-align:center;position:relative;overflow:hidden}
.match-hero::before{content:'';position:absolute;top:-40px;left:50%;transform:translateX(-50%);width:200px;height:200px;background:radial-gradient(circle,rgba(0,255,135,.08),transparent 70%);pointer-events:none}
.match-league{font-size:.52rem;font-weight:600;letter-spacing:2.5px;text-transform:uppercase;color:var(--t2);margin-bottom:12px}
.match-teams{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:12px}
.team-block{flex:1;text-align:center}
.team-name{font-size:.82rem;font-weight:800;color:var(--wh);line-height:1.3}
.vs-block{flex-shrink:0;text-align:center}
.vs-score{font-size:2.4rem;font-weight:900;color:var(--wh);letter-spacing:-2px;line-height:1}
.vs-sep{font-size:.6rem;font-weight:700;color:var(--t2);letter-spacing:2px}

.pred-card{border-radius:18px;padding:18px;margin-bottom:8px;position:relative;overflow:hidden}
.pred-card.reliable{background:linear-gradient(135deg,rgba(0,255,135,.08),rgba(0,230,118,.04));border:1px solid rgba(0,255,135,.2)}
.pred-card.solid{background:linear-gradient(135deg,rgba(79,142,247,.07),rgba(59,124,240,.03));border:1px solid rgba(79,142,247,.18)}
.pred-card.avoid{background:linear-gradient(135deg,rgba(255,69,58,.07),rgba(244,67,54,.03));border:1px solid rgba(255,69,58,.18)}
.pred-card.monitor{background:var(--s);border:1px solid var(--bdr)}
.pred-card.sure{background:linear-gradient(135deg,rgba(0,255,135,.15),rgba(0,230,118,.08));border:1px solid rgba(0,255,135,.35);box-shadow:0 0 25px rgba(0,255,135,.1)}
.tip-main{font-size:1.6rem;font-weight:900;letter-spacing:-0.5px;margin-bottom:2px}
.tip-prob{font-size:.65rem;font-weight:700;color:var(--t3);margin-bottom:12px}
.tip-reason{font-size:.68rem;color:var(--t3);line-height:1.6;background:rgba(0,0,0,.2);border-radius:10px;padding:10px 12px;margin-top:10px}

.pb-row{margin-bottom:10px}
.pb-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:4px}
.pb-label{font-size:.64rem;color:var(--t3);font-weight:600}
.pb-val{font-size:.68rem;font-weight:800}
.pb-track{height:5px;background:rgba(255,255,255,.04
