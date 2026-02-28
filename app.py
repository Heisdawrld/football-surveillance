from flask import Flask, render_template_string, request, jsonify, Response
import os, json
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
# CSS & LAYOUT (HIGH END)
# ─────────────────────────────────────────────────────────────

CSS = """
:root{
  --bg:#03050a;--s:#080c14;--s2:#0d1220;--s3:#131929;
  --g:#00ff87;--b:#4f8ef7;--r:#ff453a;--w:#ff9f0a;--pu:#bf5af2;--gold:#ffd60a;
  --t:#4a5568;--t2:#718096;--t3:#94a3b8;--wh:#f0f4f8;
  --bdr:rgba(255,255,255,.04);--bdr2:rgba(255,255,255,.08);
  --card-bg:linear-gradient(145deg,#0a0f1a,#080c14);
}
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
body{background:var(--bg);color:var(--t3);font-family:-apple-system,BlinkMacSystemFont,'Inter',sans-serif;font-size:13px;padding-bottom:80px}
a{text-decoration:none;color:inherit}
.nav{position:sticky;top:0;z-index:99;background:rgba(3,5,10,.9);backdrop-filter:blur(20px);border-bottom:1px solid var(--bdr);padding:14px 16px;display:flex;justify-content:space-between;align-items:center}
.logo{font-weight:900;color:var(--wh);font-size:1.1rem}
.logo span{color:var(--g)}
.shell{max-width:500px;margin:0 auto;padding:0 14px}
.hero{padding:20px 0;text-align:center}
.hero-title{font-size:2.5rem;font-weight:900;color:var(--wh);line-height:1}
.hero-sub{color:var(--t2);font-size:0.7rem;text-transform:uppercase;letter-spacing:1px;margin-bottom:10px}

/* TILES & CARDS */
.lg-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:20px}
.lg-tile{background:var(--card-bg);border:1px solid var(--bdr);border-radius:16px;padding:15px;display:block;transition:.2s}
.lg-tile:active{transform:scale(0.98);border-color:var(--g)}
.lt-name{font-weight:800;color:var(--wh);margin-bottom:2px}
.lt-c{font-size:0.6rem;color:var(--t2);text-transform:uppercase}

.fx-row{display:flex;align-items:center;padding:12px;border-bottom:1px solid var(--bdr);background:var(--s);gap:10px}
.fx-row:first-child{border-top-left-radius:16px;border-top-right-radius:16px}
.fx-row:last-child{border-bottom:none;border-bottom-left-radius:16px;border-bottom-right-radius:16px}
.fx-time{font-size:0.6rem;color:var(--t2);width:40px;text-align:center}
.fx-teams{flex:1;font-weight:700;color:var(--wh)}
.fx-tag{font-size:0.55rem;font-weight:800;padding:2px 6px;border-radius:4px;background:var(--bdr2);color:var(--t2)}

/* MATCH PAGE */
.match-hero{background:linear-gradient(180deg,rgba(0,255,135,.05),transparent);border:1px solid var(--bdr2);border-radius:20px;padding:20px;text-align:center;margin-bottom:15px}
.match-league{font-size:0.6rem;color:var(--t2);letter-spacing:2px;text-transform:uppercase;margin-bottom:10px}
.match-teams{display:flex;justify-content:space-between;align-items:center}
.team-name{font-weight:900;font-size:1rem;color:var(--wh);flex:1}
.vs-sep{font-weight:700;color:var(--t2);font-size:0.7rem}

.pred-card{padding:18px;border-radius:18px;margin-bottom:8px;position:relative;overflow:hidden}
.pred-card.reliable{background:linear-gradient(135deg,rgba(0,255,135,.1),rgba(0,255,135,.02));border:1px solid rgba(0,255,135,.2)}
.tip-main{font-size:1.4rem;font-weight:900;margin:4px 0}
.tip-prob{font-size:0.7rem;color:var(--t3)}
.tip-reason{margin-top:10px;padding:10px;background:rgba(0,0,0,.2);border-radius:8px;font-size:0.7rem;line-height:1.5}

.card{background:var(--s);border:1px solid var(--bdr);border-radius:16px;padding:15px;margin-bottom:8px}
.card-title{font-size:0.6rem;font-weight:700;color:var(--t2);letter-spacing:1px;text-transform:uppercase;margin-bottom:8px}
.badge{padding:4px 8px;border-radius:50px;font-size:0.55rem;font-weight:800;text-transform:uppercase}
.bg-green{background:rgba(0,255,135,.15);color:var(--g);border:1px solid rgba(0,255,135,.3)}

.empty{text-align:center;padding:40px;color:var(--t2)}
.back{display:inline-block;padding:10px 0;font-size:0.7rem;font-weight:700;color:var(--t2)}
"""

LAYOUT = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>ProPred God Mode</title>
<style>""" + CSS + """</style>
</head>
<body>
<nav class="nav">
  <div class="logo">PRO<span>PRED</span></div>
  <a href="/live" style="font-size:0.6rem;font-weight:800;color:var(--r)">● LIVE</a>
</nav>
<div class="shell">{{ content|safe }}</div>
</body>
</html>"""

# ─────────────────────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────────────────────

@app.route("/")
def index():
    # Fetch today's fixtures
    fixtures = sportmonks.get_fixtures_today()
    
    # Simple grouping
    leagues = {}
    for f in fixtures:
        l_name = f.get('league', {}).get('name', 'Unknown League')
        if l_name not in leagues: leagues[l_name] = []
        leagues[l_name].append(f)
    
    content = f'''
    <div class="hero">
        <div class="hero-sub">God Mode Active</div>
        <div class="hero-title">{len(fixtures)} MATCHES</div>
    </div>
    <div class="search-wrap"></div>
    '''
    
    if not fixtures:
        content += '<div class="empty">No fixtures found for today.</div>'
    
    for lg_name, matches in leagues.items():
        content += f'<div class="card-title" style="margin-top:20px;margin-left:5px">{lg_name}</div><div class="fx-wrap">'
        for m in matches:
            h_name = next((p['name'] for p in m['participants'] if p['meta']['location']=='home'), "Home")
            a_name = next((p['name'] for p in m['participants'] if p['meta']['location']=='away'), "Away")
            time_str = kickoff_label(m.get('starting_at'))
            
            content += f'''
            <a href="/match/{m['id']}" class="fx-row">
                <div class="fx-time">{time_str}</div>
                <div class="fx-teams">{h_name} <span style="color:var(--t2);font-weight:400">vs</span> {a_name}</div>
                <div class="fx-tag">ANALYZE</div>
            </a>
            '''
        content += '</div>'
        
    return render_template_string(LAYOUT, content=content)

@app.route("/match/<int:match_id>")
def match_page(match_id):
    try:
        # 1. FETCH GOD MODE DATA
        data = sportmonks.get_match_details(match_id)
        if not data:
            return render_template_string(LAYOUT, content='<div class="empty">Match data unavailable. API limit or ID error.</div>')
            
        # 2. RUN BRAIN
        analysis = match_predictor.analyze_match(data)
        if not analysis:
            return render_template_string(LAYOUT, content='<div class="empty">Not enough data to generate Smart Prediction.</div>')

        tips = analysis['tips']
        # Default objects to prevent crash
        rec = tips.get('recommended') or {"selection": "Analyzing...", "prob": 0, "odds": 0}
        safe = tips.get('safest') or {"selection": "--", "prob": 0, "odds": 0}
        risky = tips.get('risky') or {"selection": "--", "prob": 0, "odds": 0}
        teams = analysis['teams']

        # 3. RENDER UI
        content = f'''
        <a href="/" class="back">← All Matches</a>
        
        <div class="match-hero">
            <div class="match-league">INTELLIGENT ANALYSIS</div>
            <div class="match-teams">
                <div class="team-name" style="text-align:right">{teams['home']}</div>
                <div class="vs-sep" style="margin:0 15px">VS</div>
                <div class="team-name" style="text-align:left">Away</div>
            </div>
        </div>

        <div class="pred-card reliable">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px">
                <div>
                    <div class="card-title" style="color:var(--g)">⚡ RECOMMENDED (VALUE)</div>
                    <div class="tip-main" style="color:var(--g)">{rec['selection']}</div>
                    <div class="tip-prob">{rec['prob']}% True Prob &middot; Odds <span style="color:var(--gold)">{rec['odds']}</span></div>
                </div>
                <span class="badge bg-green">BEST VALUE</span>
            </div>
            <div class="tip-reason">{analysis['analysis']}</div>
        </div>

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:10px">
            
            <div class="card" style="margin:0;border-color:rgba(79,142,247,.3);background:linear-gradient(135deg,rgba(79,142,247,.08),transparent)">
                <div class="card-title" style="color:var(--b)">🛡️ BANKER</div>
                <div style="font-size:0.9rem;font-weight:900;color:var(--b);line-height:1.2;margin-bottom:4px">{safe['selection']}</div>
                <div style="font-size:0.6rem;color:var(--t2)">{safe['prob']}% &middot; {safe['odds']}</div>
            </div>

            <div class="card" style="margin:0;border-color:rgba(255,69,58,.3);background:linear-gradient(135deg,rgba(255,69,58,.08),transparent)">
                <div class="card-title" style="color:var(--r)">💣 HIGH REWARD</div>
                <div style="font-size:0.9rem;font-weight:900;color:var(--r);line-height:1.2;margin-bottom:4px">{risky['selection']}</div>
                <div style="font-size:0.6rem;color:var(--t2)">{risky['prob']}% &middot; {risky['odds']}</div>
            </div>
        </div>
        '''

        return render_template_string(LAYOUT, content=content)

    except Exception as e:
        import traceback; traceback.print_exc()
        return render_template_string(LAYOUT, content=f'<div class="empty">System Error: {str(e)}</div>')

@app.route("/live")
def live_page():
    lives = sportmonks.get_livescores()
    content = '<div class="hero"><div class="hero-title">LIVE NOW</div></div>'
    if not lives:
        content += '<div class="empty">No live matches.</div>'
    else:
        for m in lives:
            h_name = next((p['name'] for p in m['participants'] if p['meta']['location']=='home'), "Home")
            a_name = next((p['name'] for p in m['participants'] if p['meta']['location']=='away'), "Away")
            content += f'<div class="fx-row"><div class="fx-time">{m.get("state",{}).get("state")}</div><div class="fx-teams">{h_name} vs {a_name}</div></div>'
    return render_template_string(LAYOUT, content=content)

@app.route("/api/morning")
def api_morning():
    return jsonify(scheduler.run_morning_job())

if __name__ == "__main__":
    app.run(debug=True, port=5000)
