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
.pb-track{height:5px;background:rgba(255,255,255,.04);border-radius:50px;overflow:hidden}
.pb-fill{height:100%;border-radius:50px;transition:width .8s cubic-bezier(.4,0,.2,1)}

.form-row{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.fd{width:24px;height:24px;border-radius:7px;display:inline-flex;align-items:center;justify-content:center;font-size:.57rem;font-weight:800;flex-shrink:0}
.fd-w{background:rgba(0,255,135,.14);color:var(--g)}
.fd-d{background:rgba(79,142,247,.14);color:var(--b)}
.fd-l{background:rgba(255,69,58,.14);color:var(--r)}
.no-data{font-size:.6rem;color:var(--t)}

.h2h-bar{display:flex;border-radius:50px;overflow:hidden;height:8px;margin:10px 0}
.h2h-h{background:var(--g);transition:flex .6s ease}
.h2h-d{background:var(--t)}
.h2h-a{background:var(--b)}
.h2h-labels{display:flex;justify-content:space-between;font-size:.6rem;font-weight:700}

.vbet{background:linear-gradient(135deg,rgba(191,90,242,.08),rgba(168,85,247,.04));border:1px solid rgba(191,90,242,.2);border-radius:14px;padding:13px 14px;margin-bottom:6px}
.vbet-label{font-size:.58rem;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;color:var(--pu)}
.vbet-val{font-size:1.1rem;font-weight:900;color:var(--wh);margin:2px 0}
.vbet-sub{font-size:.6rem;color:var(--t3)}

.ref-card{background:var(--s2);border:1px solid var(--bdr);border-radius:14px;padding:13px 14px}
.ref-signal{display:inline-flex;align-items:center;gap:4px;padding:3px 9px;border-radius:50px;font-size:.58rem;font-weight:700;letter-spacing:.8px}
.ref-hot{background:rgba(255,69,58,.1);color:var(--r);border:1px solid rgba(255,69,58,.2)}
.ref-ok{background:rgba(0,255,135,.08);color:var(--g);border:1px solid rgba(0,255,135,.15)}

.lineup-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px}
.lineup-team{font-size:.58rem;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:var(--t2);margin-bottom:6px}
.lineup-player{font-size:.68rem;color:var(--t3);padding:4px 0;border-bottom:1px solid var(--bdr);line-height:1.4}
.lineup-player:last-child{border-bottom:none}

.event-row{display:flex;align-items:center;gap:8px;padding:7px 0;border-bottom:1px solid var(--bdr);font-size:.68rem}
.event-row:last-child{border-bottom:none}
.ev-min{width:28px;font-size:.62rem;font-weight:700;color:var(--t2);flex-shrink:0}
.ev-icon{font-size:.8rem;flex-shrink:0}
.ev-name{flex:1;color:var(--t3)}
.ev-side{font-size:.56rem;color:var(--t2)}

.card{background:var(--s);border:1px solid var(--bdr);border-radius:16px;padding:16px;margin-bottom:8px}
.card-title{font-size:.6rem;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:var(--t2);margin-bottom:12px;display:flex;align-items:center;gap:6px}
.card-title-icon{font-size:.85rem}

.badge{display:inline-flex;align-items:center;gap:3px;font-size:.55rem;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;padding:3px 9px;border-radius:50px}
.bg-green{background:rgba(0,255,135,.1);color:var(--g);border:1px solid rgba(0,255,135,.2)}
.bg-blue{background:rgba(79,142,247,.1);color:var(--b);border:1px solid rgba(79,142,247,.2)}
.bg-red{background:rgba(255,69,58,.1);color:var(--r);border:1px solid rgba(255,69,58,.2)}
.bg-orange{background:rgba(255,159,10,.1);color:var(--w);border:1px solid rgba(255,159,10,.2)}
.bg-muted{background:rgba(74,85,104,.1);color:var(--t2);border:1px solid var(--bdr2)}
.bg-pu{background:rgba(191,90,242,.1);color:var(--pu);border:1px solid rgba(191,90,242,.2)}

.tracker-hero{background:linear-gradient(135deg,rgba(0,255,135,.07),rgba(79,142,247,.04));border:1px solid rgba(0,255,135,.14);border-radius:20px;padding:22px;margin-bottom:10px}
.big-num{font-size:3.5rem;font-weight:900;line-height:1;letter-spacing:-2px;color:var(--wh)}
.big-label{font-size:.52rem;font-weight:600;letter-spacing:2px;text-transform:uppercase;color:var(--t2);margin-top:3px}
.perf-row{display:flex;justify-content:space-between;align-items:center;padding:11px 0;border-bottom:1px solid var(--bdr);font-size:.72rem}
.perf-row:last-child{border-bottom:none}
.result-row{display:flex;align-items:center;gap:10px;padding:10px 0;border-bottom:1px solid var(--bdr)}
.result-row:last-child{border-bottom:none}
.win-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0}

.acca-row{display:flex;justify-content:space-between;align-items:center;padding:13px 14px;border-bottom:1px solid var(--bdr);gap:10px}
.acca-row:last-child{border-bottom:none}
.acca-odds-box{background:linear-gradient(135deg,rgba(0,255,135,.12),rgba(0,230,118,.06));border:1px solid rgba(0,255,135,.2);border-radius:14px;padding:14px;text-align:center;margin-top:10px}
.acca-odds-num{font-size:2rem;font-weight:900;color:var(--g);letter-spacing:-1px}

.back{display:inline-flex;align-items:center;gap:5px;font-size:.58rem;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:var(--t2);padding:14px 0 16px;transition:color .18s}
.back:hover{color:var(--wh)}
.empty{text-align:center;padding:60px 20px;color:var(--t2);font-size:.75rem;line-height:2}
.empty-icon{font-size:2.5rem;display:block;margin-bottom:12px;opacity:.4}
.expand-toggle{display:flex;justify-content:space-between;align-items:center;cursor:pointer;padding:12px 0;font-size:.7rem;font-weight:700;color:var(--t3);user-select:none;transition:color .18s}
.expand-toggle:hover{color:var(--wh)}
.expand-arrow{transition:transform .3s;font-size:.7rem;color:var(--t2)}
.expand-arrow.open{transform:rotate(180deg)}
.expand-body{overflow:hidden;max-height:0;transition:max-height .45s ease}
.expand-body.open{max-height:3000px}
.info-row{display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid var(--bdr);font-size:.69rem}
.info-row:last-child{border-bottom:none}
.info-lbl{color:var(--t2)}
.info-val{color:var(--wh);font-weight:700}

@keyframes fadeUp{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:translateY(0)}}
@keyframes spin{to{transform:rotate(360deg)}}
.up{animation:fadeUp .3s ease both}
.d1{animation-delay:.05s}.d2{animation-delay:.1s}.d3{animation-delay:.15s}.d4{animation-delay:.2s}
.spin{animation:spin .8s linear infinite}
"""

# ─────────────────────────────────────────────────────────────
# HTML LAYOUT
# ─────────────────────────────────────────────────────────────

LAYOUT = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="ProPred">
<meta name="theme-color" content="#00ff87">
<link rel="manifest" href="/manifest.json">
<title>ProPred NG</title>
<style>""" + CSS + """</style>
</head>
<body>
<nav>
  <div class="nav-inner">
    <div class="logo">
      <span class="logo-pro">PRO</span><span class="logo-pred">PRED</span>
      <span class="logo-ng">NG</span>
    </div>
    <div class="nav-right">
      <a href="/live" class="live-count" id="live-count" style="display:none">● LIVE</a>
      <a href="/" class="npill {{ 'on' if page=='home' else '' }}">Leagues</a>
      <a href="/acca" class="npill {{ 'on' if page=='acca' else '' }}">ACCA</a>
      <a href="/tracker" class="npill {{ 'on' if page=='tracker' else '' }}">Tracker</a>
    </div>
  </div>
</nav>
<div class="shell">{{ content|safe }}</div>
<script>
// Expandable sections
document.querySelectorAll('.expand-toggle').forEach(el=>{
  el.addEventListener('click',()=>{
    const b=el.nextElementSibling,ar=el.querySelector('.expand-arrow');
    if(b){b.classList.toggle('open');}
    if(ar){ar.classList.toggle('open');}
  });
});

// Animate prob bars on scroll
const io=new IntersectionObserver(es=>{
  es.forEach(e=>{
    if(e.isIntersecting){
      const el=e.target;
      el.style.width=el.dataset.w+'%';
      io.unobserve(el);
    }
  });
},{threshold:0.1});
document.querySelectorAll('.pb-fill').forEach(el=>{
  el.dataset.w=parseFloat(el.style.width)||0;
  el.style.width='0%';
  io.observe(el);
});

// Live match count
fetch('/api/live-count').then(r=>r.json()).then(d=>{
  if(d.count>0){
    const el=document.getElementById('live-count');
    if(el){el.textContent='● '+d.count+' LIVE';el.style.display='';}
  }
}).catch(()=>{});

// Search
const si=document.getElementById('lsearch');
if(si){
  const sc=document.querySelector('.s-clear');
  si.addEventListener('input',function(){
    const q=this.value.toLowerCase().trim();
    if(sc) sc.classList.toggle('vis',q.length>0);
    document.querySelectorAll('.lg-tile').forEach(t=>{
      const n=(t.dataset.n||'').toLowerCase();
      t.style.display=(!q||n.includes(q))?'':'none';
    });
    document.querySelectorAll('.sec-hd').forEach(h=>{
      const g=h.nextElementSibling;
      if(g&&g.classList.contains('lg-grid')){
        const vis=[...g.querySelectorAll('.lg-tile')].some(t=>t.style.display!=='none');
        h.style.display=vis?'':'none';
        g.style.display=vis?'':'none';
      }
    });
  });
  if(sc) sc.addEventListener('click',()=>{
    si.value='';sc.classList.remove('vis');
    document.querySelectorAll('.lg-tile,.sec-hd').forEach(e=>e.style.display='');
  });
}
</script>
</body>
</html>"""

# ─────────────────────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────────────────────

@app.route("/")
def index():
    cards = get_all_cards(3)
    leagues = {}
    name_count = {}
    for c in cards:
        lkey = f'{c["league_id"]}_{c["country"]}'
        if lkey not in leagues:
            leagues[lkey] = {
                "id": c["league_id"], "name": c["league"], "icon": c["icon"],
                "country": c["country"], "tier": c["tier"],
                "fixtures": [], "live": 0, "has_today": False, "has_tomorrow": False
            }
            name_count[c["league"]] = name_count.get(c["league"], 0) + 1
        leagues[lkey]["fixtures"].append(c)
        if c["is_live"]:                     leagues[lkey]["live"] += 1
        if c.get("date_label") == "TODAY":   leagues[lkey]["has_today"] = True
        if c.get("date_label") == "TOMORROW":leagues[lkey]["has_tomorrow"] = True

    for lkey, lg in leagues.items():
        if name_count.get(lg["name"], 1) > 1:
            lg["display_name"] = f'{lg["name"]} ({lg["country"]})'
        else:
            lg["display_name"] = lg["name"]

    today_fx = sum(1 for c in cards if c.get("date_label") == "TODAY")
    tmrw_fx = sum(1 for c in cards if c.get("date_label") == "TOMORROW")
    total_live = sum(1 for c in cards if c["is_live"])

    content = f'''
    <div class="hero up">
      <div class="hero-eyebrow">Football Intelligence · 3-Day View</div>
      <div class="hero-title">LEAGUES<br><span>AHEAD</span></div>
      <div class="hero-stats">
        <div class="hstat"><div class="hstat-n">{today_fx}</div><div class="hstat-l">Today</div></div>
        <div class="hstat"><div class="hstat-n">{tmrw_fx}</div><div class="hstat-l">Tomorrow</div></div>
        <div class="hstat"><div class="hstat-n" style="color:var(--r)">{total_live}</div><div class="hstat-l">Live</div></div>
        <div class="hstat"><div class="hstat-n">{len(leagues)}</div><div class="hstat-l">Leagues</div></div>
      </div>
    </div>
    <div class="search-wrap up d1">
      <span class="s-icon">🔍</span>
      <input id="lsearch" class="search-inp" type="text" placeholder="Search league or country...">
      <span class="s-clear">✕</span>
    </div>'''

    sorted_leagues = sorted(leagues.items(), key=lambda x: (x[1]["tier"], -x[1]["live"], -(1 if x[1]["has_today"] else 0), -len(x[1]["fixtures"])))
    tiers = {}
    for lkey, lg in sorted_leagues:
        tiers.setdefault(lg["tier"], []).append((lkey, lg))
    tier_labels = {1:"⭐ Top Leagues", 2:"🌍 Major Leagues", 3:"🔭 More Leagues"}

    for tier in sorted(tiers.keys()):
        label = tier_labels.get(tier, "More")
        content += f'<div class="sec-hd up d2"><span class="sec-hd-dot"></span>{label}</div><div class="lg-grid up d3">'
        for lkey, lg in tiers[tier]:
            live_str = f'<span style="color:var(--r);font-size:.5rem;font-weight:700;display:block">● {lg["live"]} LIVE</span>' if lg["live"] else ""
            day_badge = '<span style="color:var(--g);font-size:.5rem;font-weight:700">TODAY</span>' if lg["has_today"] else ('<span style="color:var(--b);font-size:.5rem;font-weight:700">TMR</span>' if lg["has_tomorrow"] else "")
            content += f'''<a href="/league/{lg["id"]}" class="lg-tile" data-n="{lg["name"].lower()} {lg["country"].lower()}">
              <span class="lt-fixtures">{len(lg["fixtures"])}</span><span class="lt-icon">{lg["icon"]}</span>
              <div class="lt-name">{lg.get("display_name", lg["name"])}</div>
              <div class="lt-country">{lg["country"]}</div>{live_str}{day_badge}
            </a>'''
        content += '</div>'

    if not leagues: content += '<div class="empty"><span class="empty-icon">⚽</span>No fixtures found.</div>'
    return render_template_string(LAYOUT, content=content, page="home")

@app.route("/league/<int:l_id>")
def league_page(l_id):
    cards = get_all_today_cards()
    lg_cards = [c for c in cards if c["league_id"] == l_id]
    if not lg_cards:
        return render_template_string(LAYOUT, content=f'<a href="/" class="back">← Leagues</a><div class="empty"><span class="empty-icon">📭</span>No fixtures today.</div>', page="league")

    groups = {}
    for c in lg_cards:
        groups.setdefault(c.get("date_label","TODAY"), []).append(c)
    for k in groups: groups[k].sort(key=lambda c: c["kickoff"] or "")
    active = request.args.get("tab", list(groups.keys())[0])

    content = f'<a href="/" class="back">← Leagues</a>'
    content += f'''<div class="hero up" style="padding:14px 0 16px"><div class="hero-eyebrow">{lg_cards[0]["icon"]} {lg_cards[0]["country"]}</div><div class="hero-title" style="font-size:2rem">{lg_cards[0]["league"]}</div><div class="hero-sub" style="margin-top:6px">{len(lg_cards)} fixtures today</div></div>'''
    content += '<div class="tabs up d1">'
    for k in groups:
        cls = "on" if k == active else ""
        content += f'<a href="/league/{l_id}?tab={k}" class="tab {cls}">{k}<span class="tab-n">{len(groups[k])}</span></a>'
    content += '</div><div class="fx-wrap up d2">'
    for c in groups.get(active, []):
        preds_raw = sportmonks.get_predictions(c["id"])
        preds = sportmonks.parse_predictions(preds_raw) if preds_raw else None
        tip, prob, tag = quick_predict(c, preds)
        tag_color = {"RELIABLE":"var(--g)","SOLID":"var(--b)","MONITOR":"var(--t2)"}.get(tag,"var(--t2)")
        sb = state_badge(c)
        sc = score_display(c) if c["is_live"] or c["is_ft"] else ""
        content += f'''<a href="/match/{c["id"]}" class="fx-row">
          <div class="fx-time">{sb}{sc}</div>
          <div class="fx-teams"><div class="fx-home">{c["home"]}</div><div class="fx-away">{c["away"]}</div></div>
          <div class="fx-right"><div class="fx-tip" style="color:{tip_color(tip)}">{tip}</div><div class="fx-prob">{prob}%</div><div class="fx-tag" style="color:{tag_color}">{tag}</div></div>
        </a>'''
    content += '</div>'
    return render_template_string(LAYOUT, content=content, page="league")

# ─────────────────────────────────────────────────────────────
# MATCH PAGE (INTELLIGENT UPDATE)
# ─────────────────────────────────────────────────────────────

@app.route("/match/<int:match_id>")
def match_page(match_id):
    try:
        # 1. Fetch Enriched Data (The Ingredients)
        enriched = sportmonks.enrich_match(match_id)
        
        # 2. Run Intelligent Analysis (The Brain)
        analysis = match_predictor.analyze_match(enriched)
        
        # 3. Unpack Results
        rec   = analysis["recommended"]
        safe  = analysis["safest"]
        risky = analysis["risky"]
        badge = analysis["badges"]
        data  = analysis["data"]
        
        # UI Mappings
        h_name = enriched.get("home_name", "Home")
        a_name = enriched.get("away_name", "Away")
        league_nm = enriched.get("league_name", "")
        kickoff = enriched.get("kickoff", "")
        state = enriched.get("state", "NS")
        score_h = enriched.get("score_home")
        score_a = enriched.get("score_away")
        
        # Badge Styling
        tag_display = badge["label"]
        tag_desc = badge["desc"]
        
        # Map Badge Type to CSS Class (for background gradient)
        # Options in CSS: reliable, solid, avoid, monitor, sure
        main_card_cls = "monitor"
        if badge["type"] == "BANKER":   main_card_cls = "sure"
        elif badge["type"] == "VOLATILE": main_card_cls = "avoid"
        elif badge["type"] == "VERSATILE": main_card_cls = "solid"
        elif badge["type"] == "GOAL_FEST": main_card_cls = "reliable"
        elif rec["conviction"] > 60:    main_card_cls = "reliable"
        
        # Map Badge Type to Badge Pill Color
        badge_pill_cls = "bg-muted"
        if badge["type"] == "BANKER":   badge_pill_cls = "bg-green"
        elif badge["type"] == "VOLATILE": badge_pill_cls = "bg-orange"
        elif badge["type"] == "VERSATILE": badge_pill_cls = "bg-blue"
        elif badge["type"] == "GOAL_FEST": badge_pill_cls = "bg-pu"
        
        # Value Edge Badge
        rec_odds = rec.get("fair_odds", 0)
        bookie_odds = enriched.get("odds", {}).get("home" if "HOME" in rec["tip"] else "away" if "AWAY" in rec["tip"] else "over_25", 0)
        edge_badge = ""
        if bookie_odds and bookie_odds > rec_odds:
            diff = round((bookie_odds - rec_odds)/rec_odds * 100, 1)
            if diff > 10:
                edge_badge = f'<span class="badge bg-green" style="margin-top:5px">+{diff}% VALUE</span>'

        # Build HTML Content
        content = '<a href="/" class="back">← Leagues</a>'
        
        # Match Hero
        is_live = state in ["1H","2H","HT","ET","LIVE"] or str(state).isdigit()
        is_ft = state in ["FT","AET","FIN"]
        status_html = f'<span class="s-badge s-live">{live_dot()} {state}</span>' if is_live else (f'<span class="s-badge s-ft">FT</span>' if is_ft else f'<span class="s-badge s-ns">{kickoff_label(kickoff)}</span>')
        score_html = f'<div class="vs-score">{score_h}<span style="color:var(--t2);font-size:1.6rem;margin:0 3px">-</span>{score_a}</div>' if (score_h is not None) else '<div class="vs-sep">VS</div>'
        
        content += f'''<div class="match-hero up">
            <div class="match-league">{league_nm}</div>
            <div style="margin:6px 0">{status_html}</div>
            <div class="match-teams">
                <div class="team-block"><div class="team-name">{h_name}</div></div>
                <div class="vs-block">{score_html}</div>
                <div class="team-block"><div class="team-name">{a_name}</div></div>
            </div>
        </div>'''
        
        # 1. Recommended Card (The Smart Part)
        conv_color = "var(--g)" if rec["conviction"] >= 60 else "var(--w)" if rec["conviction"] >= 40 else "var(--r)"
        content += f'''<div class="pred-card {main_card_cls} up d1">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px">
                <div>
                    <div style="font-size:.52rem;font-weight:700;letter-spacing:2.5px;text-transform:uppercase;color:var(--t2);margin-bottom:5px">RECOMMENDED TIP</div>
                    <div class="tip-main" style="color:{tip_color(rec["tip"])}">{rec["tip"]}</div>
                    <div class="tip-prob">{rec["prob"]}% probability &middot; Fair odds: <span style="color:var(--gold)">{rec["fair_odds"]}</span></div>
                    {edge_badge}
                </div>
                <span class="badge {badge_pill_cls}" style="white-space:nowrap;flex-shrink:0">{tag_display}</span>
            </div>
            <div style="display:flex;gap:8px;margin-bottom:10px">
                <div style="flex:1;background:rgba(0,0,0,.2);border-radius:8px;padding:8px 10px">
                    <div style="font-size:.52rem;color:var(--t2);margin-bottom:2px;letter-spacing:1px;text-transform:uppercase">Conviction</div>
                    <div style="font-size:1rem;font-weight:900;color:{conv_color}">{rec["conviction"]}<span style="font-size:.6rem;color:var(--t2)">/100</span></div>
                </div>
                <div style="flex:1;background:rgba(0,0,0,.2);border-radius:8px;padding:8px 10px">
                    <div style="font-size:.52rem;color:var(--t2);margin-bottom:2px;letter-spacing:1px;text-transform:uppercase">Volatility</div>
                    <div style="font-size:.75rem;font-weight:800;color:var(--wh)">{badge["volatility"]} <span style="font-size:.5rem;font-weight:400;color:var(--t2)">(Chaos)</span></div>
                </div>
            </div>
            <div class="tip-reason">{rec["reason"]}</div>
        </div>'''
        
        # 2. Safe & Risky Grid
        content += f'''<div style="display:grid;grid-template-columns:1fr 1fr;gap:7px;margin-bottom:8px" class="up d2">
            <div class="card" style="margin:0;border-color:rgba(79,142,247,.25);background:linear-gradient(135deg,rgba(79,142,247,.07),transparent)">
                <div class="card-title">SAFEST TIP</div>
                <div style="font-size:.9rem;font-weight:900;color:{tip_color(safe["tip"])};line-height:1.2">{safe["tip"]}</div>
                <div style="font-size:.62rem;color:var(--t2);margin-top:3px">{safe["prob"]}% &middot; ~{safe["fair_odds"]}</div>
            </div>
            <div class="card" style="margin:0;border-color:rgba(191,90,242,.25);background:linear-gradient(135deg,rgba(191,90,242,.07),transparent)">
                <div class="card-title">RISKY PICK</div>
                <div style="font-size:.9rem;font-weight:900;color:{tip_color(risky["tip"])};line-height:1.2">{risky["tip"]}</div>
                <div style="font-size:.62rem;color:var(--t2);margin-top:3px">{risky["prob"]}% &middot; ~{risky["fair_odds"]}</div>
            </div>
        </div>'''
        
        # 3. Probabilities & Stats
        content += f'''<div class="card up d2">
            <div class="card-title">Win Probabilities</div>
            {prob_bar("Home Win", data["home_win_prob"], "green")}
            {prob_bar("Draw", data["draw_prob"], "blue")}
            {prob_bar("Away Win", data["away_win_prob"], "orange")}
        </div>
        
        <div class="card up d3">
            <div class="card-title">xG Battle</div>
            <div style="display:flex;gap:16px;margin-top:10px;padding-top:10px;border-top:1px solid var(--bdr)">
                <div><div style="font-size:.5rem;color:var(--t2);text-transform:uppercase;letter-spacing:1.5px">Home xG</div><div style="font-size:1.2rem;font-weight:900;color:var(--g)">{data["xg_h"]}</div></div>
                <div><div style="font-size:.5rem;color:var(--t2);text-transform:uppercase;letter-spacing:1.5px">Away xG</div><div style="font-size:1.2rem;font-weight:900;color:var(--b)">{data["xg_a"]}</div></div>
            </div>
        </div>'''
        
        # 4. Form (Keep existing logic)
        h_form = enriched.get("home_form", [])
        a_form = enriched.get("away_form", [])
        content += f'''<div class="card up d3">
            <div class="card-title">Recent Form</div>
            <div class="info-row">
                <div><div class="info-lbl">{h_name}</div></div>
                <div class="form-row">{form_dots(h_form)}</div>
            </div>
            <div class="info-row">
                <div><div class="info-lbl">{a_name}</div></div>
                <div class="form-row">{form_dots(a_form)}</div>
            </div>
        </div>'''

        # 5. H2H & Referee (Legacy Data)
        h2h = enriched.get("h2h_summary")
        if h2h and h2h.get("total",0)>0:
            hw_p = round(h2h["home_wins"]/h2h["total"]*100)
            content += f'''<div class="card up d3"><div class="card-title">Head to Head</div>
                <div class="info-row"><div class="info-lbl">Matches</div><div class="info-val">{h2h["total"]}</div></div>
                <div class="info-row"><div class="info-lbl">Home Win %</div><div class="info-val">{hw_p}%</div></div>
                <div class="info-row"><div class="info-lbl">Avg Goals</div><div class="info-val">{h2h["avg_goals"]}</div></div>
            </div>'''
            
        ref = enriched.get("referee")
        if ref:
            is_hot = ref.get("high_card_game", False)
            sig = f'<span class="ref-signal ref-hot">High Cards</span>' if is_hot else f'<span class="ref-signal ref-ok">Normal</span>'
            content += f'''<div class="card up d4"><div class="card-title">Referee</div>
                <div class="info-row"><div class="info-lbl">Name</div><div class="info-val">{ref.get("name")}</div></div>
                <div class="info-row"><div class="info-lbl">Avg Yellows</div><div class="info-val">{ref.get("avg_yellow")}</div></div>
                <div style="margin-top:8px">{sig}</div>
            </div>'''
            
        # Log to DB
        try:
            database.log_prediction(
                match_id=match_id, league_id=enriched.get("league_id",0),
                league_name=league_nm, home_team=h_name, away_team=a_name,
                match_date=kickoff[:16], market=rec["tip"], probability=rec["prob"],
                fair_odds=rec["fair_odds"], confidence=rec["conviction"], 
                xg_home=data["xg_h"], xg_away=data["xg_a"],
                tag=tag_display, reliability_score=rec["conviction"])
        except: pass

        return render_template_string(LAYOUT, content=content, page="match")
        
    except Exception as e:
        import traceback; traceback.print_exc()
        return render_template_string(LAYOUT, content=f'<div class="empty">Analysis Error: {str(e)}</div>', page="match")

@app.route("/live")
def live_page():
    lives = sportmonks.get_livescores()
    content = '<div class="hero up"><div class="hero-eyebrow">Real-Time</div><div class="hero-title">LIVE <span>NOW</span></div></div>'
    if not lives:
        content += '<div class="empty"><span class="empty-icon">📡</span>No live matches.</div>'
    else:
        by_league = {}
        for fx in lives:
            c = build_fixture_card(fx)
            by_league.setdefault(c["league"] or "Unknown", []).append(c)
        for lg, cards in by_league.items():
            meta = get_league_meta(lg)
            content += f'<div class="sec-hd">{meta["icon"]} {lg}</div><div class="fx-wrap">'
            for c in cards:
                content += f'''<a href="/match/{c["id"]}" class="fx-row">
                  <div class="fx-time"><div class="s-badge s-live">{live_dot()} {c["state"]}</div><div style="margin-top:3px">{score_display(c)}</div></div>
                  <div class="fx-teams"><div class="fx-home">{c["home"]}</div><div class="fx-away">{c["away"]}</div></div>
                </a>'''
            content += '</div>'
    return render_template_string(LAYOUT, content=content, page="live")

@app.route("/acca")
def acca_page():
    cards = get_all_cards(3)
    ns_cards = [c for c in cards if c["is_ns"]]
    picks = []
    for c in ns_cards[:50]:
        preds_raw = sportmonks.get_predictions(c["id"])
        preds = sportmonks.parse_predictions(preds_raw) if preds_raw else None
        tip, prob, tag = quick_predict(c, preds)
        if tag in ("RELIABLE","SOLID") and prob >= 60:
            picks.append({"id":c["id"], "home":c["home"], "away":c["away"], "tip":tip, "prob":prob, "league":c["league"], "icon":c["icon"]})
    
    picks.sort(key=lambda x: x["prob"], reverse=True)
    top5 = picks[:5]
    
    content = '<div class="hero up"><div class="hero-eyebrow">Auto-Selected</div><div class="hero-title">ACCA <span>BUILDER</span></div></div>'
    if not top5:
        content += '<div class="empty"><span class="empty-icon">🎯</span>No high-confidence picks.</div>'
    else:
        content += '<div class="card up d1">'
        for p in top5:
            content += f'''<div class="acca-row">
              <div style="flex:1"><div style="font-size:.6rem;color:var(--t2)">{p["icon"]} {p["league"]}</div><div style="font-weight:700;color:var(--wh)">{p["home"]} vs {p["away"]}</div></div>
              <div style="text-align:right"><div style="font-weight:800;color:{tip_color(p["tip"])}">{p["tip"]}</div><span class="badge bg-green">RELIABLE</span></div>
            </div>'''
        content += '</div>'
    return render_template_string(LAYOUT, content=content, page="acca")

@app.route("/tracker")
def tracker_page():
    try: stats = database.get_tracker_stats()
    except: stats = {"hit_rate":0,"roi":0,"total":0,"wins":0,"losses":0,"pending":0}
    
    hr_color = "var(--g)" if stats["hit_rate"] >= 55 else "var(--r)"
    content = f'''<div class="tracker-hero up">
        <div style="display:flex;justify-content:space-between">
            <div><div class="big-num" style="color:{hr_color}">{stats["hit_rate"]}%</div><div class="big-label">Hit Rate</div></div>
            <div style="text-align:right"><div class="big-num" style="font-size:2.2rem;color:var(--wh)">{stats["roi"]}%</div><div class="big-label">ROI</div></div>
        </div>
        <div style="display:flex;gap:14px;margin-top:16px">
            <div class="hstat"><div class="hstat-n">{stats["total"]}</div><div class="hstat-l">Settled</div></div>
            <div class="hstat"><div class="hstat-n" style="color:var(--g)">{stats["wins"]}</div><div class="hstat-l">Wins</div></div>
            <div class="hstat"><div class="hstat-n" style="color:var(--r)">{stats["losses"]}</div><div class="hstat-l">Losses</div></div>
        </div>
    </div>'''
    return render_template_string(LAYOUT, content=content, page="tracker")

@app.route("/api/live-count")
def api_live_count():
    lives = sportmonks.get_livescores()
    return jsonify({"count": len(lives) if lives else 0})

@app.route("/api/morning")
def api_morning():
    return jsonify(scheduler.run_morning_job())

@app.route("/api/settle")
def api_settle():
    return jsonify(scheduler.run_settlement_job())

@app.route("/manifest.json")
def pwa_manifest():
    manifest = {
        "name": "ProPred NG", "short_name": "ProPred", "start_url": "/",
        "display": "standalone", "background_color": "#03050a", "theme_color": "#00ff87",
        "icons": [{"src": "/static/icon.png","sizes":"192x192","type":"image/png"}]
    }
    return Response(json.dumps(manifest), mimetype="application/json")

if __name__ == "__main__":
    app.run(debug=True, port=5000)
