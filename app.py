from flask import Flask, render_template_string, request
import requests
from match_predictor import API_KEY, BASE_URL, get_match_analysis

app = Flask(__name__)

LAYOUT = """
<script src="https://cdn.tailwindcss.com"></script>
<body class="bg-[#05070a] text-zinc-300 font-sans italic p-4 md:p-10">
    <div class="max-w-4xl mx-auto border-b border-white/5 pb-6 mb-10 flex justify-between items-center">
        <h1 class="text-2xl text-white font-black italic tracking-tighter uppercase">PRO <span class="text-green-500">PREDICTOR</span></h1>
        <div class="text-[10px] text-zinc-500 font-black"><a href="/">HUB</a> | <a href="/acca">ACCA HUB</a></div>
    </div>
    <div class="max-w-4xl mx-auto">{{ content | safe }}</div>
</body>
"""

@app.route("/")
def home():
    # iSportsApi 'schedule' endpoint
    url = f"{BASE_URL}schedule?api_key={API_KEY}"
    try:
        matches = requests.get(url).json().get('data', [])
    except: matches = []
    
    content = '<h2 class="text-green-500 text-[10px] font-black tracking-[0.4em] mb-8 uppercase text-center italic">iSPORTS DATA FEED</h2>'
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
    if "error" in res: return "Data Synchronizing..."
    
    content = f'''
    <div class="mb-6"><a href="/" class="text-zinc-600 font-bold text-[10px] uppercase">← RETURN</a></div>
    
    <div class="text-center mb-8">
        <span class="bg-green-500/10 text-green-500 border border-green-500/20 px-4 py-1 rounded-full text-[9px] font-black tracking-[0.3em] uppercase">{res['tag']}</span>
    </div>

    <div class="bg-gradient-to-br from-[#10141d] to-[#07090e] p-8 rounded-[2.5rem] border border-white/5 mb-6 shadow-2xl relative">
        <span class="text-[9px] font-black text-zinc-500 tracking-widest uppercase italic block mb-4">🔵 Recommended Tip (Best Value)</span>
        <h2 class="text-3xl font-black text-white italic uppercase tracking-tighter mb-4">{res['rec']['t']}</h2>
        <div class="text-4xl font-black text-green-500 italic mb-4">{res['rec']['p']}%</div>
        <ul class="space-y-2 border-t border-white/5 pt-4">
            {"".join([f'<li class="text-[10px] text-zinc-400 font-bold uppercase flex items-center gap-2"><span class="w-1 h-1 bg-green-500 rounded-full"></span>{r}</li>' for r in res['rec']['r']])}
        </ul>
    </div>

    <div class="grid grid-cols-2 gap-4 mb-10">
        <div class="bg-[#0f1218] p-6 rounded-[2rem] border border-white/5">
            <span class="text-[8px] text-zinc-600 font-black uppercase block mb-2 italic">🟢 Alternate (Safest)</span>
            <h4 class="text-sm font-black text-white italic uppercase mb-1">{res['alt']['t']}</h4>
            <p class="text-2xl font-black text-white italic opacity-40">{res['alt']['p']}%</p>
        </div>
        <div class="bg-[#0f1218] p-6 rounded-[2rem] border border-white/5">
            <span class="text-[8px] text-zinc-600 font-black uppercase block mb-2 italic tracking-widest">🔴 High Risk</span>
            <h4 class="text-sm font-black text-red-500 italic uppercase mb-1">{res['risk']['t']}</h4>
            <p class="text-2xl font-black text-red-500 italic opacity-40">{res['risk']['p']}%</p>
        </div>
    </div>

    <div class="bg-black/20 p-8 rounded-[2.5rem] border border-white/5 mb-20 shadow-inner">
        <h3 class="text-[10px] font-black text-zinc-700 uppercase tracking-[0.4em] mb-8 text-center italic underline decoration-zinc-800">Match Insights & Form</h3>
        <div class="grid grid-cols-2 gap-10 mb-10 text-center border-b border-white/5 pb-8">
            <div><p class="text-[8px] text-zinc-600 font-black uppercase mb-2">Avg Goals</p><p class="text-xl font-black text-white">{res['stats']['h_avg']} vs {res['stats']['a_avg']}</p></div>
            <div><p class="text-[8px] text-zinc-600 font-black uppercase mb-2">Volatility</p><p class="text-xl font-black text-yellow-500">{res['stats']['vol']}</p></div>
        </div>
        <div class="space-y-4 text-[9px] font-black uppercase tracking-widest">
            <div class="flex justify-between"><span>Home Form</span><div class="flex gap-1">{"".join([f'<span class="w-5 h-5 rounded flex items-center justify-center {"bg-green-500 text-black" if f=="W" else "bg-zinc-800 text-zinc-500"}">{f}</span>' for f in res['h_form']])}</div></div>
            <div class="flex justify-between"><span>Away Form</span><div class="flex gap-1">{"".join([f'<span class="w-5 h-5 rounded flex items-center justify-center {"bg-green-500 text-black" if f=="W" else "bg-zinc-800 text-zinc-500"}">{f}</span>' for f in res['a_form']])}</div></div>
        </div>
    </div>
    '''
    return render_template_string(LAYOUT, content=content)
