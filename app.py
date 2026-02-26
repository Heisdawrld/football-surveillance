from flask import Flask, render_template_string, request
import requests
from datetime import datetime, timedelta
import match_predictor

app = Flask(__name__)

LAYOUT = """
<script src="https://cdn.tailwindcss.com"></script>
<body class="bg-[#05070a] text-zinc-300 font-sans italic p-4 md:p-10">
    <div class="max-w-4xl mx-auto flex justify-between items-center mb-10 border-b border-white/5 pb-6 uppercase font-black">
        <h1 class="text-2xl text-white italic tracking-tighter uppercase underline decoration-green-500">PRO <span class="text-green-500">PREDICTOR</span></h1>
        <div class="flex gap-4 text-[10px] text-zinc-500 tracking-widest"><a href="/">HUB</a> <a href="/acca">ACCA HUB</a></div>
    </div>
    <div class="max-w-4xl mx-auto">{{ content | safe }}</div>
</body>
"""

@app.route("/")
def home():
    # We are pulling a 7-day window to make sure the Hub is NEVER empty
    start = (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')
    end = (datetime.now() + timedelta(days=5)).strftime('%Y-%m-%d')
    
    # APIFootball v3 format: action=get_events & from/to dates
    url = f"https://apiv3.apifootball.com/?action=get_events&from={start}&to={end}&APIkey={match_predictor.FOOTBALL_API_KEY}"
    
    try:
        r = requests.get(url)
        matches = r.json()
    except:
        matches = []
    
    content = '<h2 class="text-green-500 text-[10px] font-black tracking-[0.4em] mb-8 uppercase text-center italic">ELITE DATA STREAM</h2>'
    
    # Check if the API returned an error message or an empty list
    if isinstance(matches, dict) and "error" in matches:
        content += f'<div class="text-center py-20"><p class="text-zinc-700 font-black uppercase mb-2">API Error</p><p class="text-[9px] text-zinc-800 uppercase">{matches["error"]}</p></div>'
    elif not matches or not isinstance(matches, list):
        content += '<div class="text-center py-20 text-zinc-700 font-black uppercase tracking-widest italic">No matches found for this period</div>'
    else:
        # Show the first 30 matches found
        for m in matches[:30]:
            m_id = m['match_id']
            h_t, a_t = m['match_hometeam_name'], m['match_awayteam_name']
            h_l, a_l = m.get('team_home_badge', ''), m.get('team_away_badge', '')
            league = m.get('league_name', 'Unknown League')
            
            content += f'''
            <a href="/match?id={m_id}" class="flex justify-between items-center p-6 bg-[#0f1218] rounded-2xl mb-3 border border-white/5 hover:border-green-500/30 transition shadow-xl relative overflow-hidden">
                <div class="absolute top-0 left-0 px-2 py-0.5 bg-white/5 text-[7px] font-black text-zinc-600 uppercase italic tracking-widest">{league}</div>
                <div class="w-2/5 flex items-center justify-end gap-3 font-bold text-white text-xs uppercase text-right"><span class="truncate">{h_t}</span><img src="{h_l}" class="w-7 h-7 object-contain"></div>
                <div class="text-[8px] text-zinc-900 font-black italic px-4 uppercase italic">ANALYZE</div>
                <div class="w-2/5 flex items-center justify-start gap-3 font-bold text-white text-xs uppercase"><img src="{a_l}" class="w-7 h-7 object-contain"><span class="truncate">{a_t}</span></div>
            </a>'''
            
    return render_template_string(LAYOUT, content=content)
