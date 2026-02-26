from flask import Flask, render_template_string, request
import requests
from datetime import datetime
import match_predictor
import os

app = Flask(__name__)

BSD_TOKEN = os.environ.get("BSD_TOKEN", "631a48f45a20b3352ea3863f8aa23baf610710e2")
BASE_URL = "https://sports.bzzoiro.com/api"

LAYOUT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
        body { font-family: 'Inter', sans-serif; background: #05070a; color: #d4d4d8; }
        .glass { background: rgba(15, 18, 24, 0.8); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.05); }
    </style>
</head>
<body class="italic">
    <div class="max-w-md mx-auto min-h-screen p-4 flex flex-col">
        <header class="flex justify-between items-center py-6 border-b border-white/5 mb-6">
            <a href="/" class="text-xl font-black text-white italic uppercase tracking-tighter tracking-widest">ELITE<span class="text-green-500">EDGE</span></a>
            <a href="/acca" class="bg-green-500/10 text-green-500 px-3 py-1.5 rounded-full text-[9px] font-black uppercase">ACCA Builder</a>
        </header>
        {{content|safe}}
    </div>
</body>
</html>
"""

@app.route("/")
def landing():
    # Adding 'OTHER' to catch all the matches you listed that aren't in the big 4
    leagues = [
        {"code": "EPL", "name": "Premier League"},
        {"code": "PD", "name": "La Liga"},
        {"code": "SA", "name": "Serie A"},
        {"code": "BL1", "name": "Bundesliga"},
        {"code": "OTHER", "name": "Other Competitions"}
    ]
    content = '<div class="py-6 text-center"><h2 class="text-2xl font-black text-white mb-8 uppercase tracking-tighter">Match Intelligence</h2>'
    for l in leagues:
        content += f'<a href="/league/{l["code"]}" class="block glass p-6 rounded-3xl mb-3 border border-white/5 font-black uppercase text-xs hover:border-green-500/30 transition">{l["name"]}</a>'
    content += '</div>'
    return render_template_string(LAYOUT, content=content)

@app.route("/league/<code>")
def league_page(code):
    headers = {"Authorization": f"Token {BSD_TOKEN}"}
    try:
        r = requests.get(f"{BASE_URL}/predictions/", headers=headers, timeout=10).json()
        all_matches = r.get("results", []) if isinstance(r, dict) else []
    except: all_matches = []

    # FILTERING LOGIC: Only keep matches that belong to the clicked league code
    filtered_matches = []
    for m in all_matches:
        match_league_id = match_predictor.get_league_id(m.get('event', {}))
        if match_league_id == code:
            filtered_matches.append(m)

    content = f'<a href="/" class="text-zinc-600 text-[10px] font-black mb-6 block uppercase tracking-widest">← Back</a>'
    content += f'<h3 class="text-green-500 text-[10px] font-black uppercase tracking-[0.3em] mb-6">{code} FIXTURES</h3>'
    
    if not filtered_matches:
        content += '<div class="py-20 text-center opacity-20 font-black uppercase text-xs">No upcoming matches for this league</div>'
    else:
        for m in filtered_matches:
            event = m.get("event", {})
            h, a = event.get("home_team", "Home"), event.get("away_team", "Away")
            content += f'''
            <a href="/match/{m["id"]}?h={h}&a={a}" class="flex justify-between items-center p-5 glass rounded-2xl mb-2 border border-white/5">
                <span class="text-[10px] font-black text-white uppercase truncate pr-4">{h} v {a}</span>
                <span class="text-green-500 text-[10px] font-black">ANALYZE →</span>
            </a>'''
    return render_template_string(LAYOUT, content=content)

# [Keep /match/<match_id> route the same as the previous bulletproof version]
