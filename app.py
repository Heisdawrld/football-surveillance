from flask import Flask, render_template_string, request
import requests
from datetime import datetime, timedelta
import match_predictor
import os

app = Flask(__name__)

# CONFIG
BSD_TOKEN = "631a48f45a20b3352ea3863f8aa23baf610710e2"
BASE_URL = "https://sports.bzzoiro.com/api"

# UPDATED: Full Global League Catalog with IDs from your source
LEAGUES = [
    {"id": 1, "name": "Premier League", "geo": "England"},
    {"id": 12, "name": "Championship", "geo": "England"},
    {"id": 4, "name": "Serie A", "geo": "Italy"},
    {"id": 5, "name": "Bundesliga", "geo": "Germany"},
    {"id": 6, "name": "Ligue 1", "geo": "France"},
    {"id": 10, "name": "Eredivisie", "geo": "Netherlands"},
    {"id": 14, "name": "Pro League", "geo": "Belgium"},
    {"id": 13, "name": "Scottish Premiership", "geo": "Scotland"},
    {"id": 2, "name": "Liga Portugal", "geo": "Portugal"},
    {"id": 11, "name": "Super Lig", "geo": "Turkey"},
    {"id": 18, "name": "MLS", "geo": "USA"},
    {"id": 15, "name": "Swiss Super League", "geo": "Switzerland"}
]

# [LAYOUT Remains Glass UI]
LAYOUT = """..."""

@app.route("/league/<l_id>")
def league_page(l_id):
    l_name = request.args.get('name', 'League')
    headers = {"Authorization": f"Token {BSD_TOKEN}"}
    
    # FETCH: Filtered specifically by League ID
    r = requests.get(f"{BASE_URL}/predictions/?league={l_id}", headers=headers).json()
    matches = r.get("results", [])

    content = f'<a href="/" class="text-zinc-600 text-[10px] font-black uppercase mb-10 block tracking-widest">← All Competitions</a>'
    content += f'<h3 class="text-green-500 font-black uppercase text-2xl italic mb-10 tracking-tighter">{l_name}</h3>'
    
    if not matches:
        content += '<div class="py-20 text-center opacity-20 font-black uppercase text-xs italic">Syncing live fixtures...</div>'
    else:
        for g in matches:
            event = g.get("event", {})
            h, a = event.get("home_team"), event.get("away_team")
            
            # --- 🕒 NEW: TIME & DATE PARSING ---
            try:
                raw_time = event.get("start_time") # Example: 2026-02-28T19:00:00Z
                dt_utc = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
                # Adjust to your local time (e.g., +1 for WAT/Nigeria)
                dt_local = dt_utc + timedelta(hours=1)
                
                display_date = dt_local.strftime("%d %b")
                display_time = dt_local.strftime("%H:%M")
            except:
                display_date, display_time = "TBA", "00:00"

            content += f'''
            <a href="/match/{g["id"]}?h={h}&a={a}&l={l_id}" class="flex justify-between items-center p-6 glass rounded-[2.5rem] mb-3 border border-white/5 shadow-xl nav-btn">
                <div class="flex flex-col">
                    <span class="text-[8px] font-black text-zinc-600 uppercase tracking-widest">{display_date}</span>
                    <span class="text-[11px] font-black text-white">{display_time}</span>
                </div>
                <span class="text-[11px] font-black text-white uppercase truncate px-4">{h} v {a}</span>
                <span class="text-green-500 font-black text-[9px]">ANALYZE →</span>
            </a>'''
            
    return render_template_string(LAYOUT, content=content)

# Use your previous /match/<match_id> route with the Poisson Engine integration
