from flask import Flask, render_template_string, request
import requests
from datetime import datetime
import match_predictor
import os

app = Flask(__name__)
BSD_TOKEN = "631a48f45a20b3352ea3863f8aa23baf610710e2"
BASE_URL = "https://sports.bzzoiro.com/api"

LEAGUE_KEYWORDS = {
    "EPL": ["liverpool", "arsenal", "manchester", "chelsea", "wolves", "newcastle", "everton", "leeds", "bournemouth", "burnley", "brentford", "villa", "watford", "sheffield", "southampton", "ipswich", "leicester"],
    "PD": ["real madrid", "barcelona", "atletico", "rayo", "levante", "alaves", "villarreal", "sevilla", "athletic"],
    "SA": ["juventus", "milan", "inter", "parma", "cagliari", "como", "lecce", "roma", "napoli", "lazio"],
    "BL1": ["bayern", "dortmund", "leverkusen", "augsburg", "koeln", "mainz", "st. pauli", "heidenheim", "union berlin", "hoffenheim"]
}

LAYOUT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <script src="https://cdn.tailwindcss.com"></script>
    <style>@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap'); body { font-family: 'Inter', sans-serif; background: #05070a; color: #d4d4d8; }</style>
</head>
<body class="p-4 italic">
    <div class="max-w-md mx-auto min-h-screen">
        <header class="py-6 border-b border-white/5 mb-6 flex justify-between items-center">
            <a href="/" class="text-xl font-black text-white italic uppercase tracking-tighter">ELITE<span class="text-green-500">EDGE</span></a>
            <div class="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
        </header>
        {{content|safe}}
    </div>
</body>
</html>
"""

@app.route("/")
def landing():
    leagues = [("EPL", "Premier League"), ("PD", "La Liga"), ("SA", "Serie A"), ("BL1", "Bundesliga")]
    content = '<div class="py-10 text-center"><h2 class="text-3xl font-black text-white italic mb-10 uppercase tracking-tighter">Quant Intelligence</h2>'
    for code, name in leagues:
        content += f'<a href="/league/{code}" class="block bg-zinc-900/50 p-8 rounded-[2rem] border border-white/5 mb-4 text-left shadow-2xl"><p class="text-[9px] text-zinc-500 font-black mb-1 uppercase tracking-widest">{code}</p><p class="text-xl font-black text-white uppercase">{name}</p></a>'
    content += '</div>'
    return render_template_string(LAYOUT, content=content)

@app.route("/league/<code>")
def league_page(code):
    headers = {"Authorization": f"Token {BSD_TOKEN}"}
    try:
        r = requests.get(f"{BASE_URL}/predictions/", headers=headers, timeout=10).json()
        all_m = r.get("results", []) if isinstance(r, dict) else []
    except: all_m = []

    matches = [m for m in all_m if any(key in m.get('event', {}).get('home_team', '').lower() for key in LEAGUE_KEYWORDS.get(code, []))]
    content = f'<a href="/" class="text-zinc-600 text-[10px] font-black uppercase mb-10 block">← Competition Hub</a>'
    if not matches:
        content += f'<div class="py-20 text-center opacity-20 font-black text-xs uppercase">No {code} fixtures live...</div>'
    else:
        content += f'<h3 class="text-green-500 font-black uppercase text-xl italic mb-10 tracking-tighter">{code} Analysis</h3>'
        for g in matches:
            h, a = g['event']['home_team'], g['event']['away_team']
            t = g['event']['start_time'][11:16]
            content += f'<a href="/match/{g["id"]}?h={h}&a={a}" class="flex justify-between items-center p-6 bg-zinc-900/40 rounded-[2rem] mb-3 border border-white/5 shadow-xl"><span class="text-[10px] font-black text-zinc-600">{t}</span><span class="text-[11px] font-black text-white uppercase truncate px-4">{h} v {a}</span><span class="text-green-500 font-black text-[9px]">ANALYZE →</span></a>'
    return render_template_string(LAYOUT, content=content)

@app.route("/match/<match_id>")
def match_display(match_id):
    h, a = request.args.get('h'), request.args.get('a')
    res = match_predictor.analyze_match(2.1, 1.4, 0.9, 1.7)
    content = f'''
    <div class="text-center mb-10">
        <span class="bg-green-500/10 text-green-500 border border-green-500/20 px-6 py-2 rounded-full text-[9px] font-black uppercase tracking-widest">{res['tag']}</span>
        <h2 class="text-2xl font-black text-white uppercase mt-12 italic tracking-tighter leading-tight">{h} <br><span class="text-zinc-800 text-sm opacity-50 not-italic">VS</span><br> {a}</h2>
    </div>
    <div class="bg-zinc-900/80 p-7 rounded-[3rem] border border-white/5 mb-4 shadow-2xl">
        <span class="text-[9px] font-black text-zinc-600 uppercase">🔵 Recommended Tip</span>
        <h2 class="text-2xl font-black text-white uppercase tracking-tighter leading-none mt-2">{res['rec']['t']}</h2>
        <div class="flex justify-between items-center mt-6 pt-6 border-t border-white/5">
            <div><p class="text-[8px] text-zinc-600 uppercase font-black">Confidence</p><p class="text-2xl font-black text-white">+{res['conf']}%</p></div>
            <div class="text-right"><p class="text-[8px] text-zinc-600 uppercase font-black">Fair Odds</p><p class="text-2xl font-black text-green-500">{res['rec']['o']}</p></div>
        </div>
    </div>
    <div class="grid grid-cols-2 gap-3 mb-10">
        <div class="bg-zinc-900/40 p-6 rounded-[2rem] border border-white/5"><span class="text-[8px] font-black text-blue-500 uppercase mb-2 block">🟢 Safe</span><p class="text-[10px] font-black text-white uppercase">{res['safe']['t']}</p></div>
        <div class="bg-zinc-900/40 p-6 rounded-[2rem] border border-white/5"><span class="text-[8px] font-black text-red-500 uppercase mb-2 block">🔴 Risk</span><p class="text-[10px] font-black text-white uppercase">{res['risk']['t']}</p></div>
    </div>
    '''
    return render_template_string(LAYOUT, content=content)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
