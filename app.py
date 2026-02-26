from flask import Flask, render_template_string, request
import requests, os, json, math
from datetime import datetime, timedelta, timezone
import match_predictor, database, external_data

app = Flask(__name__)
database.init_db()

BSD_TOKEN = "631a48f45a20b3352ea3863f8aa23baf610710e2"
BASE_URL  = "https://sports.bzzoiro.com/api"

LEAGUES = [
    {"id": 1,  "name": "Premier League",  "country": "England",  "icon": "ENG"},
    {"id": 12, "name": "Championship",    "country": "England",  "icon": "ENG"},
    {"id": 3,  "name": "La Liga",         "country": "Spain",    "icon": "ESP"},
    {"id": 4,  "name": "Serie A",         "country": "Italy",    "icon": "ITA"},
    {"id": 5,  "name": "Bundesliga",      "country": "Germany",  "icon": "GER"},
    {"id": 14, "name": "Pro League",      "country": "Belgium",  "icon": "BEL"},
    {"id": 18, "name": "MLS",             "country": "USA",      "icon": "USA"},
    {"id": 2,  "name": "Liga Portugal",   "country": "Portugal", "icon": "POR"},
    {"id": 11, "name": "Süper Lig",       "country": "Turkey",   "icon": "TUR"},
    {"id": 13, "name": "Scottish Prem",   "country": "Scotland", "icon": "SCO"},
    {"id": 20, "name": "Liga MX",         "country": "Mexico",   "icon": "MEX"},
]
LEAGUE_MAP = {l["id"]: l for l in LEAGUES}
WAT_OFFSET = 1

def api_get(path, params=None):
    headers = {"Authorization": f"Token {BSD_TOKEN}"}
    try:
        r = requests.get(f"{BASE_URL}{path}", headers=headers, params=params, timeout=12)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[API Error] {path} -> {e}")
        return {}

def parse_dt(raw):
    try:
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc) + timedelta(hours=WAT_OFFSET)
    except:
        return datetime.now(tz=timezone.utc)

def now_wat():
    return datetime.now(tz=timezone.utc) + timedelta(hours=WAT_OFFSET)

def group_by_date(matches):
    today    = now_wat().date()
    tomorrow = today + timedelta(days=1)
    groups   = {}
    for m in matches:
        dt  = parse_dt(m.get("event", {}).get("event_date", ""))
        d   = dt.date()
        key = "TODAY" if d == today else "TOMORROW" if d == tomorrow else dt.strftime("%-d %b").upper()
        groups.setdefault(key, []).append((dt, m))
    for k in groups:
        groups[k].sort(key=lambda x: x[0])
    return groups

def form_dots(form_list):
    if not form_list:
        return '<span style="color:var(--t);font-size:0.62rem">No data</span>'
    html = '<div class="dots">'
    for r in list(form_list)[-5:]:
        r = r.upper()
        html += f'<span class="dot dot-{r}">{r}</span>'
    return html + '</div>'

def prob_bar(label, pct, color="green"):
    c = {"green":"var(--g)","blue":"var(--b)","warn":"var(--w)"}.get(color,"var(--g)")
    return f'''<div class="prow">
      <div class="plabel"><span>{label}</span><span class="pval">{pct}%</span></div>
      <div class="ptrack"><div class="pfill" style="width:{pct}%;background:{c}"></div></div>
    </div>'''

def tag_badge(tag):
    cls = {"ELITE VALUE":"badge-green","STRONG PICK":"badge-green",
           "QUANT EDGE":"badge-blue","MONITOR":"badge-muted"}.get(tag,"badge-muted")
    return f'<span class="badge {cls}">{tag}</span>'

def trend_icon(t):
    return {"RISING":"up","FALLING":"down","STABLE":"right"}.get(t,"right")

def result_badge(r):
    if r == "WIN":  return '<span class="badge badge-green">WIN</span>'
    if r == "LOSS": return '<span class="badge badge-red">LOSS</span>'
    return '<span class="badge badge-muted">PENDING</span>'

LAYOUT = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>ProPredictor</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{--bg:#07090e;--s:#0e1219;--s2:#141820;--g:#00e676;--b:#2979ff;--w:#ff6d00;--r:#f44336;--t:#8892a4;--wh:#e8edf5;--bdr:rgba(255,255,255,0.07)}
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
html{scroll-behavior:smooth}
body{background:var(--bg);color:var(--t);font-family:Inter,sans-serif;font-size:13px;min-height:100vh;padding-bottom:90px}
a{text-decoration:none;color:inherit}
nav{position:sticky;top:0;z-index:99;background:rgba(7,9,14,0.92);backdrop-filter:blur(18px);border-bottom:1px solid var(--bdr)}
.nav-i{max-width:480px;margin:0 auto;display:flex;justify-content:space-between;align-items:center;padding:12px 14px}
.logo{font-family:"Bebas Neue",sans-serif;font-size:1.3rem;letter-spacing:1px;color:var(--wh)}
.logo em{color:var(--g);font-style:normal}
.nav-links{display:flex;gap:5px}
.npill{font-size:0.6rem;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;padding:5px 11px;border-radius:50px;border:1px solid var(--bdr);color:var(--t);transition:all .2s}
.npill:hover,.npill.on{border-color:var(--g);color:var(--g);background:rgba(0,230,118,.08)}
.shell{max-width:480px;margin:0 auto;padding:0 14px}
.card{background:var(--s);border:1px solid var(--bdr);border-radius:16px;padding:18px;margin-bottom:10px}
.badge{display:inline-block;font-size:0.58rem;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;padding:3px 9px;border-radius:50px}
.badge-green{background:rgba(0,230,118,.12);color:var(--g);border:1px solid rgba(0,230,118,.25)}
.badge-blue{background:rgba(41,121,255,.12);color:var(--b);border:1px solid rgba(41,121,255,.25)}
.badge-muted{background:rgba(136,146,164,.08);color:var(--t);border:1px solid var(--bdr)}
.badge-red{background:rgba(244,67,54,.12);color:var(--r);border:1px solid rgba(244,67,54,.25)}
.display{font-family:"Bebas Neue",sans-serif;color:var(--wh);line-height:1}
.eyebrow{font-size:0.58rem;font-weight:600;letter-spacing:2px;text-transform:uppercase;color:var(--t);margin-bottom:4px}
.sep{font-size:0.58rem;letter-spacing:2.5px;text-transform:uppercase;color:var(--t);padding:18px 0 10px;border-bottom:1px solid var(--bdr);margin-bottom:12px}
.prow{margin-bottom:10px}
.plabel{display:flex;justify-content:space-between;margin-bottom:4px;font-size:0.68rem}
.pval{color:var(--wh);font-weight:600}
.ptrack{height:4px;background:rgba(255,255,255,.05);border-radius:50px;overflow:hidden}
.pfill{height:100%;border-radius:50px;transition:width .7s cubic-bezier(.4,0,.2,1)}
.dots{display:flex;gap:4px}
.dot{width:22px;height:22px;border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:0.6rem;font-weight:700}
.dot-W{background:rgba(0,230,118,.15);color:var(--g)}
.dot-D{background:rgba(41,121,255,.15);color:var(--b)}
.dot-L{background:rgba(244,67,54,.15);color:var(--r)}
.tabs{display:flex;gap:7px;overflow-x:auto;padding-bottom:4px;margin-bottom:14px;scrollbar-width:none}
.tabs::-webkit-scrollbar{display:none}
.tab{flex-shrink:0;font-size:0.65rem;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;padding:6px 13px;border-radius:50px;border:1px solid var(--bdr);color:var(--t);transition:all .2s;white-space:nowrap}
.tab:hover,.tab.on{border-color:var(--g);color:var(--g);background:rgba(0,230,118,.08)}
.fix-wrap{background:var(--s);border:1px solid var(--bdr);border-radius:16px;overflow:hidden;margin-bottom:10px}
.fix-row{display:flex;align-items:center;padding:13px 16px;border-bottom:1px solid var(--bdr);transition:background .15s;cursor:pointer}
.fix-row:last-child{border-bottom:none}
.fix-row:hover{background:rgba(255,255,255,.02)}
.fix-time{font-size:0.7rem;color:var(--t);min-width:38px;font-weight:600}
.fix-teams{flex:1;text-align:center;font-size:0.85rem;font-weight:700;color:var(--wh);padding:0 8px}
.fix-vs{color:var(--t);font-size:0.65rem;margin:0 4px}
.fix-arr{color:var(--g);font-size:0.7rem;min-width:14px;text-align:right}
.back{display:inline-flex;align-items:center;gap:5px;font-size:0.65rem;font-weight:600;letter-spacing:1.5px;text-transform:uppercase;color:var(--t);padding:14px 0 20px;transition:color .2s}
.back:hover{color:var(--wh)}
.rec-box{background:linear-gradient(135deg,rgba(0,230,118,.07),rgba(41,121,255,.05));border:1px solid rgba(0,230,118,.18);border-radius:18px;padding:20px;margin-bottom:10px}
.rec-market{font-family:"Bebas Neue",sans-serif;font-size:2rem;color:var(--wh);letter-spacing:.5px;margin:6px 0 2px}
.rec-pct{font-family:"Bebas Neue",sans-serif;font-size:3.2rem;color:var(--g);letter-spacing:-1px;line-height:1}
.sgrid{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:10px}
.sgrid3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-bottom:10px}
.sbox{background:var(--s2);border:1px solid var(--bdr);border-radius:13px;padding:14px;text-align:center}
.sval{font-family:"Bebas Neue",sans-serif;font-size:1.8rem;color:var(--wh);line-height:1}
.sval.g{color:var(--g)}.sval.b{color:var(--b)}.sval.w{color:var(--w)}.sval.r{color:var(--r)}
.slbl{font-size:0.58rem;letter-spacing:1.5px;text-transform:uppercase;color:var(--t);margin-top:3px}
.mbar-wrap{position:relative;height:8px;background:rgba(255,255,255,.06);border-radius:50px;overflow:hidden;margin:10px 0}
.mbar-h{position:absolute;left:0;top:0;height:100%;background:var(--g);border-radius:50px}
.mbar-a{position:absolute;right:0;top:0;height:100%;background:var(--b);border-radius:50px}
.cring{position:relative;width:72px;height:72px;flex-shrink:0}
.cring-num{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-family:"Bebas Neue",sans-serif;font-size:1rem;color:var(--wh)}
.edge{font-size:0.6rem;font-weight:700;padding:2px 8px;border-radius:50px}
.edge-pos{background:rgba(0,230,118,.12);color:var(--g)}
.edge-neg{background:rgba(244,67,54,.12);color:var(--r)}
.h2h-row{display:flex;justify-content:space-between;align-items:center;padding:8px 12px;border-bottom:1px solid var(--bdr);font-size:0.72rem}
.h2h-row:last-child{border-bottom:none}
.h2h-score{font-family:"Bebas Neue",sans-serif;font-size:1.1rem;color:var(--wh)}
.inj-item{display:flex;align-items:center;gap:8px;padding:7px 0;border-bottom:1px solid var(--bdr);font-size:0.7rem}
.inj-item:last-child{border-bottom:none}
.inj-dot{width:7px;height:7px;border-radius:50%;background:var(--r);flex-shrink:0}
.inj-dot.susp{background:var(--w)}
.stats-row{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--bdr);font-size:0.72rem}
.stats-row:last-child{border-bottom:none}
.stats-val{font-weight:700;color:var(--wh)}
.tracker-row{display:flex;justify-content:space-between;align-items:center;padding:11px 14px;border-bottom:1px solid var(--bdr);font-size:0.72rem}
.tracker-row:last-child{border-bottom:none}
.league-card{background:var(--s);border:1px solid var(--bdr);border-radius:16px;padding:18px 20px;margin-bottom:8px;display:flex;justify-content:space-between;align-items:center;transition:border-color .2s}
.league-card:hover{border-color:rgba(255,255,255,.15)}
.acca-row{display:flex;justify-content:space-between;align-items:center;padding:13px 16px;border-bottom:1px solid var(--bdr)}
.acca-row:last-child{border-bottom:none}
.acca-match{font-size:0.82rem;font-weight:700;color:var(--wh)}
.acca-mkt{font-size:0.6rem;letter-spacing:1.5px;text-transform:uppercase;color:var(--t);margin-top:2px}
.acca-odds{font-family:"Bebas Neue",sans-serif;font-size:1.3rem;color:var(--g)}
.empty{text-align:center;padding:50px 20px;color:var(--t);font-size:0.75rem;letter-spacing:1px}
.info-box{background:var(--s2);border:1px solid var(--bdr);border-radius:12px;padding:12px 14px;font-size:0.7rem;line-height:1.6;color:var(--t);margin-bottom:8px}
.info-box strong{color:var(--wh)}
@keyframes fu{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:translateY(0)}}
.fu{animation:fu .35s ease both}
.d1{animation-delay:.05s}.d2{animation-delay:.1s}.d3{animation-delay:.15s}.d4{animation-delay:.2s}
</style>
</head>
<body>
<nav>
  <div class="nav-i">
    <a href="/" class="logo">PRO<em>PRED</em></a>
    <div class="nav-links">
      <a href="/" class="npill {{ "on" if page=="home" else "" }}">Leagues</a>
      <a href="/acca" class="npill {{ "on" if page=="acca" else "" }}">ACCA</a>
      <a href="/tracker" class="npill {{ "on" if page=="tracker" else "" }}">Track</a>
    </div>
  </div>
</nav>
<div class="shell">{{ content|safe }}</div>
</body>
</html>'''

@app.route("/")
def index():
    c = '<div style="padding:28px 0 16px" class="fu"><p class="eyebrow">Football Intelligence</p><h1 class="display" style="font-size:2.8rem;margin-top:4px">SELECT<br>YOUR LEAGUE</h1></div>'
    for i, l in enumerate(LEAGUES):
        c += f'<a href="/league/{l["id"]}" class="league-card fu d{min(i+1,4)}"><div><p class="eyebrow">{l["icon"]} · {l["country"]}</p><p class="display" style="font-size:1.5rem;margin-top:3px">{l["name"]}</p></div><span style="color:var(--t);font-size:1.1rem">›</span></a>'
    return render_template_string(LAYOUT, content=c, page="home")

@app.route("/league/<int:l_id>")
def league_page(l_id):
    league  = LEAGUE_MAP.get(l_id, {"name":"League","icon":"—","country":""})
    data    = api_get("/predictions/")
    matches = [m for m in data.get("results",[]) if m.get("event",{}).get("league",{}).get("id") == l_id]
    back    = '<a href="/" class="back">← Leagues</a>'
    if not matches:
        return render_template_string(LAYOUT, content=f'{back}<div class="empty">No fixtures available</div>', page="league")
    groups    = group_by_date(matches)
    date_keys = list(groups.keys())
    active    = request.args.get("tab", date_keys[0] if date_keys else "TODAY")
    tabs = '<div class="tabs">' + ''.join(f'<a href="/league/{l_id}?tab={k}" class="tab {"on" if k==active else ""}">{k} ({len(groups[k])})</a>' for k in date_keys) + '</div>'
    rows = '<div class="fix-wrap">'
    for dt, m in groups.get(active, []):
        e = m.get("event",{}); h,a = e.get("home_team","?"), e.get("away_team","?"); mid = m.get("id",0)
        rows += f'<a href="/match/{mid}" class="fix-row"><span class="fix-time">{dt.strftime("%H:%M")}</span><span class="fix-teams">{h}<span class="fix-vs">vs</span>{a}</span><span class="fix-arr">›</span></a>'
    rows += '</div>'
    c = f'{back}<div class="fu" style="margin-bottom:20px"><p class="eyebrow">{league["icon"]} · {league["country"]}</p><h2 class="display" style="font-size:2rem;margin-top:4px">{league["name"]}</h2><p style="font-size:0.65rem;color:var(--t);margin-top:5px;letter-spacing:1px">{len(matches)} FIXTURES</p></div>{tabs}{rows}'
    return render_template_string(LAYOUT, content=c, page="league")

@app.route("/match/<int:match_id>")
def match_display(match_id):
    data   = api_get(f"/predictions/{match_id}/")
    if not data:
        return render_template_string(LAYOUT, content='<a href="/" class="back">← Home</a><div class="empty">Match data unavailable</div>', page="match")
    event  = data.get("event",{}); league = event.get("league",{})
    l_id   = league.get("id",1); l_info = LEAGUE_MAP.get(l_id, {"name":league.get("name",""),"icon":"","country":""})
    h      = event.get("home_team","Home"); a = event.get("away_team","Away")
    dt     = parse_dt(event.get("event_date",""))
    res    = match_predictor.analyze_match(data, l_id)
    if not res:
        return render_template_string(LAYOUT, content=f'<a href="/league/{l_id}" class="back">← {l_info["name"]}</a><div class="empty">Analysis unavailable</div>', page="match")
    enriched = external_data.enrich_match(data)
    try:
        database.log_prediction(
            match_id=match_id, league_id=l_id, league_name=l_info.get("name",""),
            home_team=h, away_team=a, match_date=dt.strftime("%Y-%m-%d %H:%M"),
            market=res["rec"]["t"], probability=res["rec"]["p"], fair_odds=res["rec"]["odds"],
            bookie_odds=None, edge=res["rec"].get("edge"), confidence=res["confidence"],
            xg_home=res["xg_h"], xg_away=res["xg_a"], likely_score=res["likely_score"])
    except: pass
    _try_settle_finished(data, match_id)
    ox=res["1x2"]; mkts=res["markets"]; mom=res["momentum"]; ups=res["upset"]; frm=res["form"]; std=res["standings"]
    conf=res["confidence"]; rc="#00e676" if conf>=60 else "#2979ff" if conf>=45 else "#ff6d00"
    r_c,cx,cy=30,36,36; circ=2*math.pi*r_c; dash=circ*(conf/100)
    edge=res["rec"].get("edge")
    edge_html=f'<span class="edge {"edge-pos" if edge and edge>0 else "edge-neg"}>{"+" if edge and edge>0 else ""}{edge}% edge</span>' if edge is not None else ""
    total_mom=max(mom["home"]+mom["away"],1); mh_w=round(mom["home"]/total_mom*100); ma_w=round(mom["away"]/total_mom*100)
    ups_color={"warn":"var(--w)","blue":"var(--b)","muted":"var(--t)"}.get(ups["color"],"var(--t)")
    c = f'<a href="/league/{l_id}" class="back">← {l_info["name"]}</a>'
    c += f'<div class="fu" style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:18px"><div>{tag_badge(res["tag"])}<h2 class="display" style="font-size:1.9rem;margin-top:8px;line-height:1.1">{h}<br><span style="color:var(--t);font-size:0.9rem;font-family:Inter,sans-serif;font-weight:400">vs</span><br>{a}</h2><p style="font-size:0.62rem;color:var(--t);margin-top:7px;letter-spacing:1.2px">{dt.strftime("%-d %b %Y")} · {dt.strftime("%H:%M")} WAT</p></div><div class="cring fu d1"><svg width="72" height="72" viewBox="0 0 72 72"><circle cx="{cx}" cy="{cy}" r="{r_c}" stroke="rgba(255,255,255,.06)" stroke-width="5" fill="none"/><circle cx="{cx}" cy="{cy}" r="{r_c}" stroke="{rc}" stroke-width="5" fill="none" stroke-dasharray="{dash:.1f} {circ:.1f}" stroke-linecap="round" transform="rotate(-90 {cx} {cy})"/></svg><div class="cring-num">{conf:.0f}%</div></div></div>'
    h_inj=enriched.get("home_injuries",[]); a_inj=enriched.get("away_injuries",[])
    if h_inj or a_inj:
        c += '<div class="card fu d1" style="border-color:rgba(244,67,54,.2)"><p class="sep" style="padding-top:0;margin-top:0;color:var(--r)">Injuries & Suspensions</p>'
        for team_name, inj_list in [(h,h_inj),(a,a_inj)]:
            if inj_list:
                c += f'<p class="eyebrow" style="margin-bottom:8px">{team_name}</p>'
                for inj in inj_list[:4]:
                    dc="inj-dot susp" if "suspend" in inj.get("type","").lower() else "inj-dot"
                    c += f'<div class="inj-item"><div class="{dc}"></div><span style="color:var(--wh)">{inj["name"]}</span><span style="margin-left:auto;font-size:0.6rem">{inj["type"]}</span></div>'
        c += '</div>'
    elif not external_data.APIFOOTBALL_KEY:
        c += '<div class="info-box fu d1">Add <strong>APIFOOTBALL_KEY</strong> environment variable to unlock H2H history, injury reports and season stats — free at api-football.com</div>'
    c += f'<div class="rec-box fu d1"><p class="eyebrow">Best Market</p><p class="rec-market">{res["rec"]["t"]}</p><div style="display:flex;align-items:baseline;gap:14px;flex-wrap:wrap"><p class="rec-pct">{res["rec"]["p"]}%</p><div><p style="font-size:0.58rem;letter-spacing:1.5px;color:var(--t)">FAIR ODDS</p><p class="display" style="font-size:1.5rem">{res["rec"]["odds"]}</p></div>{"<div>"+edge_html+"</div>" if edge_html else ""}</div><p style="font-size:0.65rem;color:var(--t);margin-top:8px">Also consider: <strong style="color:var(--wh)">{res["second"]["t"]}</strong> ({res["second"]["p"]}%)</p></div>'
    c += f'<div class="sgrid fu d2"><div class="sbox"><p class="sval g">{res["xg_h"]}</p><p class="slbl">xG {h.split()[0]}</p></div><div class="sbox"><p class="sval b">{res["xg_a"]}</p><p class="slbl">xG {a.split()[0]}</p></div></div>'
    c += f'<div class="card fu d2" style="text-align:center;padding:14px 18px"><p class="eyebrow">Most Likely Score</p><p class="display" style="font-size:2.4rem;margin-top:2px">{res["likely_score"]}</p></div>'
    c += f'<div class="card fu d2"><p class="sep" style="padding-top:0;margin-top:0">1 x 2</p>{prob_bar("Home Win",ox["home"])}{prob_bar("Draw",ox["draw"],"blue")}{prob_bar("Away Win",ox["away"],"warn")}</div>'
    c += f'<div class="card fu d3"><p class="sep" style="padding-top:0;margin-top:0">Goal Markets</p>{prob_bar("Over 1.5",mkts["over_15"])}{prob_bar("Over 2.5",mkts["over_25"])}{prob_bar("Over 3.5",mkts["over_35"])}{prob_bar("Under 2.5",mkts["under_25"],"warn")}{prob_bar("BTTS",mkts["btts"],"blue")}</div>'
    h2h_sum=enriched.get("h2h_summary")
    if h2h_sum:
        total_h2h=h2h_sum["total"]; hw=h2h_sum["home_wins"]; dr=h2h_sum["draws"]; aw=h2h_sum["away_wins"]
        hw_w=round(hw/total_h2h*100); dr_w=round(dr/total_h2h*100); aw_w=round(aw/total_h2h*100)
        c += f'<div class="card fu d3"><p class="sep" style="padding-top:0;margin-top:0">Head to Head - Last {total_h2h}</p><div class="sgrid3" style="margin-bottom:14px"><div class="sbox"><p class="sval g">{hw}</p><p class="slbl">{h.split()[0]} wins</p></div><div class="sbox"><p class="sval">{dr}</p><p class="slbl">Draws</p></div><div class="sbox"><p class="sval b">{aw}</p><p class="slbl">{a.split()[0]} wins</p></div></div><div style="display:flex;height:6px;border-radius:3px;overflow:hidden;margin-bottom:10px"><div style="flex:{hw_w};background:var(--g)"></div><div style="flex:{dr_w};background:var(--t)"></div><div style="flex:{aw_w};background:var(--b)"></div></div><div style="display:flex;justify-content:space-between;font-size:0.62rem;margin-bottom:12px"><span>Avg goals <strong style="color:var(--wh)">{h2h_sum["avg_goals"]}</strong></span><span>Over 2.5 <strong style="color:var(--wh)">{h2h_sum["over_25_pct"]}%</strong></span><span>BTTS <strong style="color:var(--wh)">{h2h_sum["btts_pct"]}%</strong></span></div>'
        for m_h2h in h2h_sum.get("matches",[]):
            hg=m_h2h.get("home_goal","?"); ag=m_h2h.get("away_goal","?"); d_str=m_h2h.get("date","")[:7]
            c += f'<div class="h2h-row"><span style="color:var(--t);min-width:50px">{d_str}</span><span style="color:var(--wh);flex:1;text-align:center;font-size:0.7rem">{m_h2h.get("home","?")} vs {m_h2h.get("away","?")}</span><span class="h2h-score">{hg}-{ag}</span></div>'
        c += '</div>'
    h_stats=enriched.get("home_stats"); a_stats=enriched.get("away_stats")
    if h_stats or a_stats:
        c += '<div class="card fu d3"><p class="sep" style="padding-top:0;margin-top:0">Season Stats</p>'
        for tn, st in [(h,h_stats),(a,a_stats)]:
            if not st: continue
            c += f'<p class="eyebrow" style="margin-bottom:8px">{tn}</p>'
            for lbl,val in [("Played",st.get("played",0)),("W/D/L",f'{st.get("wins",0)}/{st.get("draws",0)}/{st.get("losses",0)}'),("Goals scored",st.get("goals_scored",0)),("Goals conceded",st.get("goals_conceded",0)),("Avg scored",st.get("avg_scored",0)),("Avg conceded",st.get("avg_conceded",0)),("Clean sheets",st.get("clean_sheets",0))]:
                c += f'<div class="stats-row"><span>{lbl}</span><span class="stats-val">{val}</span></div>'
            c += '<div style="height:12px"></div>'
        c += '</div>'
    c += f'<div class="card fu d3"><p class="sep" style="padding-top:0;margin-top:0">Momentum</p><div style="display:flex;justify-content:space-between;font-size:0.68rem;margin-bottom:6px"><span style="color:var(--g)">{h.split()[0]} ({mom["home"]}%)</span><span style="color:var(--b)">{a.split()[0]} ({mom["away"]}%)</span></div><div class="mbar-wrap"><div class="mbar-h" style="width:{mh_w}%"></div><div class="mbar-a" style="width:{ma_w}%"></div></div><p style="font-size:0.65rem;color:var(--t);margin-top:8px">{mom["narrative"]}</p></div>'
    c += f'<div class="sgrid fu d4"><div class="card" style="margin:0"><p class="eyebrow">Upset Risk</p><p class="display" style="font-size:1.8rem;color:{ups_color};margin:6px 0">{ups["index"]}</p><p style="font-size:0.6rem;color:{ups_color};letter-spacing:1px">{ups["label"]}</p></div><div class="card" style="margin:0"><p class="eyebrow">Style</p><p style="font-size:0.68rem;line-height:1.5;color:var(--t);margin-top:6px">{res["style"]}</p></div></div>'
    c += f'<div class="card fu d4"><p class="sep" style="padding-top:0;margin-top:0">Form - Last 5</p><div style="display:flex;flex-direction:column;gap:12px;margin-bottom:16px"><div style="display:flex;justify-content:space-between;align-items:center"><span style="font-size:0.78rem;font-weight:700;color:var(--wh)">{h}</span>{form_dots(frm["home"])}</div><div style="display:flex;justify-content:space-between;align-items:center"><span style="font-size:0.78rem;font-weight:700;color:var(--wh)">{a}</span>{form_dots(frm["away"])}</div></div><div style="display:flex;gap:20px;padding-top:14px;border-top:1px solid var(--bdr)"><div><p class="eyebrow">Standing</p><p class="display" style="font-size:1.4rem">{"#"+str(std["home"]) if std["home"] else "—"}</p><p style="font-size:0.6rem;color:var(--t)">{h.split()[0]}</p></div><div><p class="eyebrow">Standing</p><p class="display" style="font-size:1.4rem">{"#"+str(std["away"]) if std["away"] else "—"}</p><p style="font-size:0.6rem;color:var(--t)">{a.split()[0]}</p></div></div></div>'
    return render_template_string(LAYOUT, content=c, page="match")

@app.route("/acca")
def acca():
    data=api_get("/predictions/"); matches=data.get("results",[]); picks,combined=match_predictor.pick_acca(matches,n=5,min_prob=52.0)
    c='<div style="padding:28px 0 16px" class="fu"><p class="eyebrow">Daily Best Picks</p><h1 class="display" style="font-size:2.8rem;margin-top:4px">ACCA<br>BUILDER</h1></div>'
    if not picks:
        c+='<div class="empty">No qualifying picks today</div>'
        return render_template_string(LAYOUT,content=c,page="acca")
    c+='<div class="fix-wrap fu d1">'
    for p in picks:
        e=p["match"].get("event",{}); h,a=e.get("home_team","?"),e.get("away_team","?"); res=p["result"]; mid=p["match"].get("id",0)
        l_info=LEAGUE_MAP.get(p["league_id"],{"icon":"—","name":""}); edge=res["rec"].get("edge")
        c+=f'<a href="/match/{mid}" class="acca-row"><div><p style="font-size:0.58rem;color:var(--t);letter-spacing:1.5px;text-transform:uppercase;margin-bottom:3px">{l_info.get("icon","—")} {l_info.get("name","")}</p><p class="acca-match">{h} vs {a}</p><p class="acca-mkt">{res["rec"]["t"]} · {res["rec"]["p"]}%{"  +"+str(edge)+"% edge" if edge and edge>0 else ""}</p></div><p class="acca-odds">{res["rec"]["odds"]}</p></a>'
    c+=f'</div><div class="rec-box fu d2" style="text-align:center;margin-top:12px"><p class="eyebrow">Combined Odds</p><p class="rec-pct" style="font-size:4rem">{combined}</p><p style="font-size:0.62rem;color:var(--t);margin-top:4px;letter-spacing:1px">{len(picks)}-FOLD ACCUMULATOR</p></div><p style="font-size:0.6rem;color:var(--t);text-align:center;padding:14px;letter-spacing:1px">Fair odds shown · Gamble responsibly</p>'
    return render_template_string(LAYOUT,content=c,page="acca")

@app.route("/tracker")
def tracker():
    stats=database.get_tracker_stats(); total=stats["total"]; wins=stats["wins"]; losses=stats["losses"]; hr=stats["hit_rate"]; pending=stats["pending"]
    c='<div style="padding:28px 0 16px" class="fu"><p class="eyebrow">Model Performance</p><h1 class="display" style="font-size:2.8rem;margin-top:4px">VALUE<br>TRACKER</h1></div>'
    if total==0:
        c+='<div class="info-box">No settled predictions yet. Browse match pages to start logging — results auto-settle when matches finish.</div>'
    else:
        hr_c="var(--g)" if hr>=60 else "var(--w)" if hr>=50 else "var(--r)"
        c+=f'<div class="sgrid fu d1"><div class="sbox"><p class="sval" style="font-size:2.8rem;color:{hr_c}">{hr}%</p><p class="slbl">Hit Rate</p></div><div class="sbox"><p class="sval g">{wins}</p><p class="slbl">Wins</p></div></div><div class="sgrid fu d1"><div class="sbox"><p class="sval r">{losses}</p><p class="slbl">Losses</p></div><div class="sbox"><p class="sval">{pending}</p><p class="slbl">Pending</p></div></div>'
    if stats["by_market"]:
        c+='<div class="card fu d2"><p class="sep" style="padding-top:0;margin-top:0">By Market</p>'
        for row in stats["by_market"]:
            mhr=round(row["wins"]/row["total"]*100,1) if row["total"] else 0
            hrc="var(--g)" if mhr>=60 else "var(--w)" if mhr>=50 else "var(--r)"
            c+=f'<div class="tracker-row"><div><p style="font-weight:700;color:var(--wh)">{row["market"]}</p><p style="font-size:0.6rem;color:var(--t)">{row["total"]} predictions · avg {round(row["avg_prob"] or 0,1)}%</p></div><p style="font-family:\'Bebas Neue\',sans-serif;font-size:1.5rem;color:{hrc}">{mhr}%</p></div>'
        c+='</div>'
    if stats["recent"]:
        c+='<div class="card fu d3"><p class="sep" style="padding-top:0;margin-top:0">Recent Results</p>'
        for row in stats["recent"]:
            hs=row.get("actual_home_score"); as_=row.get("actual_away_score")
            sc=f"{hs}-{as_}" if hs is not None else "—"
            c+=f'<div class="tracker-row"><div style="flex:1"><p style="font-size:0.72rem;font-weight:700;color:var(--wh)">{row["home_team"]} vs {row["away_team"]}</p><p style="font-size:0.6rem;color:var(--t)">{row["market"]} · {row["probability"]}% · {row["league_name"]}</p></div><div style="text-align:right"><p style="font-size:0.65rem;color:var(--t);margin-bottom:3px">{sc}</p>{result_badge(row["result"])}</div></div>'
        c+='</div>'
    return render_template_string(LAYOUT,content=c,page="tracker")

def _try_settle_finished(api_data, match_id):
    try:
        event=api_data.get("event",{}); status=event.get("status","")
        hs=event.get("home_score"); as_=event.get("away_score")
        if status=="finished" and hs is not None and as_ is not None:
            for p in database.get_recent_pending():
                if p["match_id"]==match_id:
                    database.settle_prediction(match_id,p["market"],int(hs),int(as_))
    except Exception as e:
        print(f"[settle] {e}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)), debug=False)
