from flask import Flask, render_template_string, request
import requests
from match_predictor import API_KEY, BASE_URL, get_match_analysis

app = Flask(__name__)

LAYOUT = """
<script src="https://cdn.tailwindcss.com"></script>
<body class="bg-[#05070a] text-zinc-300 font-sans italic p-4 md:p-10">
    <div class="max-w-4xl mx-auto border-b border-white/5 pb-6 mb-10 flex justify-between items-center">
        <h1 class="text-2xl text-white font-black italic uppercase tracking-tighter">PRO <span class="text-green-500">PREDICTOR</span></h1>
        <div class="text-[10px] text-zinc-500 font-black"><a href="/">HUB</a></div>
    </div>
    <div class="max-w-4xl mx-auto">{{ content | safe }}</div>
</body>
"""

@app.route("/")
def home():
    # iSportsApi Schedule Endpoint
    url = f"{BASE_URL}schedule?api_key={API_KEY}"
    try:
        response = requests.get(url).json()
        matches = response.get('data', [])
    except:
        matches = []
    
    content = '<h2 class="text-green-500 text-[10px] font-black tracking-[0.4em] mb-8 uppercase text-center italic">iSPORTS LIVE FEED</h2>'
    
    if not matches:
        content += '<div class="text-center py-20 text-zinc-700 font-black uppercase tracking-widest">No Matches Found</div>'
    else:
        for m in matches[:15]:
            m_id = m['matchId']
            content += f'''
            <a href="/match?id={m_id}" class="flex justify-between items-center p-6 bg-[#0f1218] rounded-2xl mb-3 border border-white/5 hover:border-green-500/30 transition">
                <div class="w-2/5 text-right font-bold text-white text-xs uppercase truncate">{m['homeName']}</div>
                <div class="text-[8px] text-zinc-900 font-black px-4 uppercase italic">ANALYZE</div>
                <div class="w-2/5 text-left font-bold text-white text-xs uppercase truncate">{m['awayName']}</div>
            </a>'''
    return render_template_string(LAYOUT, content=content)

@app.route("/match")
def match():
    res = get_match_analysis(request.args.get("id"))
    if "error" in res: return "Syncing Match Data..."
    
    # ... (Keep the match display logic from the Master Prompt)
    return render_template_string(LAYOUT, content="Match Analysis Logic Here") # Finalize with Master Prompt UI
