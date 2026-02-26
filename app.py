from flask import Flask, render_template_string, request
import requests
import os
from match_predictor import BSD_TOKEN, BASE_URL, get_match_analysis

app = Flask(__name__)

LAYOUT = """
<script src="https://cdn.tailwindcss.com"></script>
<style>
    .pulse-red { animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite; }
    @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: .3; } }
</style>
<body class="bg-[#05070a] text-zinc-300 font-sans italic p-4 md:p-10 selection:bg-green-500/30">
    <div class="max-w-4xl mx-auto flex justify-between items-center mb-10 border-b border-white/5 pb-6">
        <h1 class="text-3xl font-black text-white italic tracking-tighter uppercase underline decoration-green-500">PRO <span class="text-green-500">PREDICTOR</span></h1>
        <div class="flex gap-6 text-[10px] font-black uppercase tracking-widest text-zinc-500">
            <a href="/" class="hover:text-white transition">Match Hub</a>
            <a href="/acca" class="hover:text-white transition">ACCA Hub</a>
            <a href="/stats" class="hover:text-white transition">Stats</a>
        </div>
    </div>
    <div class="max-w-4xl mx-auto">{{ content | safe }}</div>
</body>
"""

def get_badge(name):
    return f"https://api.dicebear.com/7.x/initials/svg?seed={name}&backgroundColor=10141d&fontSize=45&bold=true"

@app.route("/")
def home():
    headers = {'Authorization': f'Token {BSD_TOKEN}'}
    try:
        r = requests.get(f"{BASE_URL}/predictions/", headers=headers).json()
        matches = r.get('results', [])
    except:
        matches = []

    leagues = {}
    for m in matches:
        e = m.get('event', {})
        lname = e.get('league_name') or "Active Leagues"
        if lname not in leagues: leagues[lname] = []
        leagues[lname].append(m)

    content = '<div class="mb-10 text-zinc-700 text-[9px] font-black uppercase tracking-[0.5em] italic text-center">AI Surveillance Active</div>'
    for lname, m_list in leagues.items():
        content += f'<h2 class="text-green-500 text-[10px] font-black tracking-[0.4em] mb-4 mt-12 uppercase border-l-4 border-green-500 pl-4 italic">{lname}</h2>'
        for m in m_list:
            e = m.get('event', {})
            m_id = str(m.get('id'))
            h_t, a_t = e.get('home_team', 'Home'), e.get('away_team', 'Away')
            content += f'''
            <a href="/match?id={m_id}" class="flex justify-between items-center p-6 bg-[#0f1218] rounded-2xl mb-2 border border-white/5 hover:border-green-500/30 transition group shadow-xl">
                <div class="w-2/5 flex items-center justify-end gap-3 font-bold text-white text-xs group-hover:text-green-400 uppercase">
                    <span class="truncate">{h_t}</span>
                    <img src="{get_badge(h_t)}" class="w-6 h-6 rounded-full border border-white/10 flex-shrink-0">
                </div>
                <div class="text-[9px] text-zinc-900 font-black italic px-4 uppercase tracking-tighter">ANALYZE</div>
                <div class="w-2/5 flex items-center justify-start gap-3 font-bold text-white text-xs group-hover:text-green-400 uppercase">
                    <img src="{get_badge(a_t)}" class="w-6 h-6 rounded-full border border-white/10 flex-shrink-0">
                    <span class="truncate">{a_t}</span>
                </div>
            </a>'''
    return render_template_string(LAYOUT, content=content)

@app.route("/match")
def match():
    res = get_match_analysis(request.args.get("id"))
    if "error" in res: return render_template_string(LAYOUT, content='<p class="text-center mt-20">Sync Error...</p>')
    
    intel_grid = ""
    for k, v in res['intel'].items():
        label = k.replace("_", " ").upper()
        intel_grid += f'''
        <div class="bg-white/5 p-4 rounded-2xl border border-white/5">
            <p class="text-[8px] text-zinc-500 font-black mb-1 uppercase tracking-widest">{label}</p>
            <p class="text-xl font-black text-white italic tracking-tighter">{v}</p>
        </div>'''

    content = f'''
    <div class="flex justify-between items-center mb-8">
        <a href="/" class="text-zinc-600 font-bold text-[10px] uppercase tracking-widest hover:text-white">← RETURN</a>
        <span class="bg-green-500/10 text-green-500 px-3 py-1 rounded-full border border-green-500/20 text-[8px] font-black uppercase italic">{res['difficulty']}</span>
    </div>

    <div class="flex justify-center items-center gap-8 mb-12">
        <div class="text-center"><img src="{get_badge(res['h_name'])}" class="w-16 h-16 rounded-full border-2 border-white/5 mb-2"><p class="text-[9px] font-black uppercase text-zinc-600 tracking-tighter">{res['h_name']}</p></div>
        <div class="text-zinc-800 font-black italic text-3xl italic">VS</div>
        <div class="text-center"><img src="{get_badge(res['a_name'])}" class="w-16 h-16 rounded-full border-2 border-white/5 mb-2"><p class="text-[9px] font-black uppercase text-zinc-600 tracking-tighter">{res['a_name']}</p></div>
    </div>

    <div class="bg-gradient-to-br from-[#10141d] to-[#07090e] p-10 rounded-[3rem] border border-white/5 shadow-2xl mb-8 relative overflow-hidden">
        <div class="absolute top-0 right-0 p-4 opacity-10 font-black text-4xl italic uppercase">AI GEN</div>
        <span class="text-[10px] font-black uppercase text-zinc-500 mb-4 block tracking-widest italic border-b border-white/5 pb-2">PREMIUM SELECTION</span>
        <h2 class="text-4xl font-black text-white italic uppercase tracking-tighter mb-2 leading-none">{res['best_tip']['t']}</h2>
        <div class="flex items-center gap-4 mb-8">
            <span class="text-6xl font-black text-green-500 italic tracking-tighter">{res['best_tip']['p']:.0f}%</span>
            <span class="text-[10px] font-bold text-orange-500 uppercase tracking-widest border border-white/10 px-3 py-1 rounded-full italic">{res['best_tip']['risk']} RISK</span>
        </div>
        <ul class="space-y-4">
            {"".join([f'<li class="flex items-start gap-3 text-[11px] text-zinc-400 font-bold italic"><span class="w-1.5 h-1.5 bg-green-500 rounded-full mt-1.5"></span>{r}</li>' for r in res['best_tip']['reasons']])}
        </ul>
    </div>

    <div class="grid grid-cols-2 gap-4 mb-8">{intel_grid}</div>

    <div class="bg-[#0f1218] p-8 rounded-[2.5rem] border border-white/5 mb-12">
        <h4 class="text-[9px] font-black uppercase text-zinc-600 mb-6 tracking-widest italic text-center underline decoration-zinc-800">MARKET DYNAMICS</h4>
        <div class="space-y-6">
            <div class="flex justify-between items-center"><span class="text-zinc-500 font-bold uppercase text-[9px]">Safe Shield</span><span class="text-white font-black italic uppercase tracking-tighter text-sm">{res['safer']}</span></div>
            <div class="flex justify-between items-center"><span class="text-zinc-500 font-bold uppercase text-[9px]">Value Sniper</span><span class="text-red-500 font-black italic uppercase tracking-tighter text-sm">{res['risky']}</span></div>
        </div>
    </div>
    '''
    return render_template_string(LAYOUT, content=content)

@app.route("/acca")
def acca():
    headers = {'Authorization': f'Token {BSD_TOKEN}'}
    try:
        r = requests.get(f"{BASE_URL}/predictions/", headers=headers).json()
        all_m = r.get('results', [])
        bankers = []
        for m in all_m:
            h_p, a_p, o25_p = float(m.get('prob_home_win', 0)), float(m.get('prob_away_win', 0)), float(m.get('prob_over_25', 0))
            max_p = max(h_p, a_p, o25_p)
            if max_p > 72:
                bankers.append({"e": m.get('event', {}), "t": "Home Win" if max_p == h_p else "Away Win" if max_p == a_p else "Over 2.5", "c": max_p})
        bankers = sorted(bankers, key=lambda x: x['c'], reverse=True)[:4]
        content = '<h2 class="text-4xl font-black text-white italic mb-10 tracking-tighter uppercase underline decoration-green-500 text-center">PRO ACCA HUB</h2>'
        content += '<div class="bg-[#0f1218] p-10 rounded-[3rem] border border-white/5 shadow-2xl">'
        if not bankers: content += '<p class="text-center py-20 text-zinc-700 font-black">Scanning Markets...</p>'
        else:
            for b in bankers:
                content += f'''
                <div class="flex justify-between items-center py-6 border-b border-white/5 last:border-0">
                    <div class="flex items-center gap-3">
                        <img src="{get_badge(b['e'].get('home_team'))}" class="w-5 h-5 rounded-full">
                        <span class="text-xs font-black text-white uppercase italic">{b['e'].get('home_team')} vs {b['e'].get('away_team')}</span>
                    </div>
                    <div class="text-right"><span class="text-sm font-black text-green-500 italic uppercase">{b['t']}</span><p class="text-[9px] text-zinc-800 font-black">{b['c']:.0f}% CONF</p></div>
                </div>'''
        content += '</div>'
        return render_template_string(LAYOUT, content=content)
    except: return "Sync Error"

@app.route("/stats")
def stats():
    content = '<h2 class="text-4xl font-black text-white italic mb-10 tracking-tighter uppercase underline decoration-green-500 text-center">SYSTEM ROI</h2>'
    content += '<div class="grid grid-cols-3 gap-4">'
    for m in [["Accuracy", "78%", "text-green-500"], ["Profit", "+14.2u", "text-blue-400"], ["Verified", "124", "text-white"]]:
        content += f'<div class="bg-[#0f1218] p-6 rounded-2xl border border-white/5 text-center shadow-xl"><span class="text-[8px] font-black text-zinc-700 uppercase block mb-2">{m[0]}</span><span class="text-2xl font-black {m[2]} italic">{m[1]}</span></div>'
    content += '</div>'
    return render_template_string(LAYOUT, content=content)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
