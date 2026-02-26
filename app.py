from flask import Flask, render_template_string, request
import requests
from datetime import datetime
import match_predictor
import os

app = Flask(__name__)
BSD_TOKEN = "631a48f45a20b3352ea3863f8aa23baf610710e2"
BASE_URL = "https://sports.bzzoiro.com/api"

# THE REAL GLOBAL MAPPING
LEAGUES = [
    {"id": 1, "code": "EPL", "name": "Premier League", "geo": "England"},
    {"id": 12, "code": "CHAM", "name": "Championship", "geo": "England"},
    {"id": 4, "code": "SA", "name": "Serie A", "geo": "Italy"},
    {"id": 5, "code": "BL1", "name": "Bundesliga", "geo": "Germany"},
    {"id": 6, "code": "L1", "name": "Ligue 1", "geo": "France"},
    {"id": 10, "code": "ERE", "name": "Eredivisie", "geo": "Netherlands"},
    {"id": 14, "code": "BPL", "name": "Pro League", "geo": "Belgium"},
    {"id": 18, "code": "MLS", "name": "MLS", "geo": "USA"},
    {"id": 11, "code": "TUR", "name": "Super Lig", "geo": "Turkey"},
    {"id": 2, "code": "POR", "name": "Liga Portugal", "geo": "Portugal"}
]

LAYOUT = """ [SAME PREMIUM UI AS BEFORE] """

@app.route("/")
def landing():
    content = '<div class="py-4 text-center"><h2 class="text-3xl font-black text-white italic mb-10 uppercase tracking-tighter">Global Intelligence</h2>'
    for l in LEAGUES:
        content += f'''
        <a href="/league/{l['id']}?name={l['name']}" class="block glass p-6 rounded-[2rem] border border-white/5 mb-3 text-left shadow-2xl nav-btn">
            <div class="flex justify-between items-center">
                <div>
                    <p class="text-[8px] text-zinc-500 font-black mb-1 uppercase tracking-widest">{l['geo']}</p>
                    <p class="text-lg font-black text-white uppercase">{l['name']}</p>
                </div>
                <span class="text-green-500 font-black text-xs italic">ID: {l['id']}</span>
            </div>
        </a>'''
    return render_template_string(LAYOUT, content=content)

@app.route("/league/<l_id>")
def league_page(l_id):
    l_name = request.args.get('name', 'League')
    headers = {"Authorization": f"Token {BSD_TOKEN}"}
    # Targeted API Call for specific League ID
    r = requests.get(f"{BASE_URL}/predictions/?league={l_id}", headers=headers).json()
    matches = r.get("results", [])

    content = f'<a href="/" class="text-zinc-600 text-[10px] font-black uppercase mb-10 block tracking-widest">← All Leagues</a>'
    content += f'<h3 class="text-green-500 font-black uppercase text-xl italic mb-8 tracking-tighter">{l_name}</h3>'
    
    for g in matches:
        event = g.get("event", {})
        raw_time = event.get("start_time", "2024-01-01T00:00:00Z")
        dt = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
        
        content += f'''
        <a href="/match/{g["id"]}?h={event.get('home_team')}&a={event.get('away_team')}&l={l_id}" class="flex justify-between items-center p-6 glass rounded-[2.5rem] mb-3 border border-white/5 shadow-xl nav-btn">
            <div class="flex flex-col"><span class="text-[8px] font-black text-zinc-600 uppercase">{dt.strftime("%d %b")}</span><span class="text-[10px] font-black text-zinc-400">{dt.strftime("%H:%M")}</span></div>
            <span class="text-[11px] font-black text-white uppercase truncate px-4">{event.get('home_team')} v {event.get('away_team')}</span>
            <span class="text-green-500 font-black text-[9px]">ANALYZE →</span>
        </a>'''
    return render_template_string(LAYOUT, content=content)

@app.route("/match/<match_id>")
def match_display(match_id):
    l_id = int(request.args.get('l', 1))
    h, a = request.args.get('h'), request.args.get('a')
    headers = {"Authorization": f"Token {BSD_TOKEN}"}
    data = requests.get(f"{BASE_URL}/predictions/{match_id}/", headers=headers).json()
    
    res = match_predictor.analyze_match(data, l_id)
    # [DASHBOARD HTML USING res]
    return render_template_string(LAYOUT, content=dashboard_html)

@app.route("/acca")
def acca():
    headers = {"Authorization": f"Token {BSD_TOKEN}"}
    r = requests.get(f"{BASE_URL}/predictions/", headers=headers).json()
    # Sort by probability of Home Win to build the slip
    top_picks = sorted(r.get("results", []), key=lambda x: x.get('prob_home', 0), reverse=True)[:5]
    
    picks_html = ""
    total_odds = 1.0
    for p in top_picks:
        odds = round((1 / p.get('prob_home', 0.5)) * 0.92, 2)
        total_odds *= odds
        picks_html += f'<div class="p-4 glass rounded-2xl mb-2 flex justify-between font-black uppercase text-[10px]"><span>{p["event"]["home_team"]}</span><span class="text-green-500">{odds}</span></div>'
    
    content = f'<div class="text-center"><h2 class="text-white text-2xl font-black mb-10 italic uppercase">Pro ACCA Slip</h2>{picks_html}<div class="mt-10 p-10 glass rounded-[3rem] border border-green-500/20"><p class="text-[10px] text-zinc-600 font-black uppercase">Combined Edge Odds</p><p class="text-5xl font-black text-green-500 mt-2 tracking-tighter">{round(total_odds, 2)}</p></div></div>'
    return render_template_string(LAYOUT, content=content)
