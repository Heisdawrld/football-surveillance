from flask import Flask, render_template_string, request
import requests
import os
from match_predictor import BSD_TOKEN, BASE_URL, get_match_analysis

app = Flask(__name__)

LAYOUT = """
<script src="https://cdn.tailwindcss.com"></script>
<body class="bg-[#05070a] text-zinc-300 font-sans italic p-4 md:p-10 selection:bg-green-500/30">
    <div class="max-w-4xl mx-auto flex justify-between items-center mb-10 border-b border-white/5 pb-6">
        <h1 class="text-3xl font-black text-white italic tracking-tighter uppercase">PRO <span class="text-green-500">PREDICTOR</span></h1>
        <div class="flex gap-4 text-[10px] font-black uppercase text-zinc-500">
            <a href="/">HUB</a> <a href="/acca">ACCA</a>
        </div>
    </div>
    <div class="max-w-4xl mx-auto">{{ content | safe }}</div>
</body>
"""

def get_badge(name):
    return f"https://api.dicebear.com/7.x/initials/svg?seed={name}&backgroundColor=10141d&bold=true"

@app.route("/")
def home():
    headers = {'Authorization': f'Token {BSD_TOKEN}'}
    try:
        r = requests.get(f"{BASE_URL}/predictions/", headers=headers).json()
        matches = r.get('results', [])
    except: matches = []
    content = '<h2 class="text-green-500 text-[10px] font-black tracking-[0.4em] mb-8 uppercase text-center italic">AI SURVEILLANCE ACTIVE</h2>'
    for m in matches:
        e = m.get('event', {}); m_id = str(m.get('id'))
        h_t, a_t = e.get('home_team', 'Home'), e.get('away_team', 'Away')
        content += f'''
        <a href="/match?id={m_id}" class="flex justify-between items-center p-6 bg-[#0f1218] rounded-2xl mb-3 border border-white/5 hover:border-green-500/30 transition">
            <div class="w-2/5 flex items-center justify-end gap-3 font-bold text-white text-xs uppercase"><span class="truncate">{h_t}</span><img src="{get_badge(h_t)}" class="w-6 h-6 rounded-full"></div>
            <div class="text-[8px] text-zinc-800 font-black italic px-4 uppercase">ANALYZE</div>
            <div class="w-2/5 flex items-center justify-start gap-3 font-bold text-white text-xs uppercase"><img src="{get_badge(a_t)}" class="w-6 h-6 rounded-full"><span class="truncate">{a_t}</span></div>
        </a>'''
    return render_template_string(LAYOUT, content=content)

@app.route("/match")
def match():
    res = get_match_analysis(request.args.get("id"))
    if "error" in res: return render_template_string(LAYOUT, content='<p class="text-center mt-20">Sync Error</p>')
    
    content = f'''
    <div class="mb-6"><a href="/" class="text-zinc-600 font-bold text-[10px] uppercase">← RETURN</a></div>
    <div class="flex justify-center items-center gap-6 mb-10">
        <div class="text-center"><img src="{get_badge(res['h_name'])}" class="w-14 h-14 rounded-full border border-white/10 mb-2"><p class="text-[8px] font-black text-zinc-500 uppercase">{res['h_name']}</p></div>
        <div class="text-zinc-800 font-black italic text-xl">VS</div>
        <div class="text-center"><img src="{get_badge(res['a_name'])}" class="w-14 h-14 rounded-full border border-white/10 mb-2"><p class="text-[8px] font-black text-zinc-500 uppercase">{res['a_name']}</p></div>
    </div>

    <div class="bg-[#10141d] p-8 rounded-[2rem] border border-white/5 mb-6 text-center relative overflow-hidden">
        <div class="absolute top-0 right-0 p-3 text-green-500/20 font-black italic text-[8px] tracking-widest">{res['tag']}</div>
        <span class="text-[9px] font-black uppercase text-zinc-500 mb-2 block tracking-widest">RECOMMENDED TIP</span>
        <h2 class="text-3xl font-black text-white italic uppercase tracking-tighter mb-1">{res['best_tip']['t']}</h2>
        <p class="text-5xl font-black text-green-500 italic tracking-tighter">{res['best_tip']['p']:.0f}% <span class="text-[10px] text-zinc-600">CONF</span></p>
    </div>

    <div class="grid grid-cols-2 gap-4 mb-6 text-center">
        <div class="bg-[#0f1218] p-5 rounded-2xl border border-white/5"><span class="text-[8px] text-zinc-500 font-black uppercase block mb-1">SAFE SHIELD</span><span class="text-xs font-black text-white italic">{res['safer']}</span></div>
        <div class="bg-[#0f1218] p-5 rounded-2xl border border-white/5"><span class="text-[8px] text-zinc-500 font-black uppercase block mb-1">HIGH VALUE</span><span class="text-xs font-black text-red-500 italic">{res['risky']}</span></div>
    </div>

    <div class="bg-black/20 p-6 rounded-2xl border border-white/5 mb-8">
        <h4 class="text-[9px] font-black uppercase text-zinc-600 mb-4 tracking-widest text-center italic text-center">PROBABILITY INSIGHTS</h4>
        <div class="flex justify-around items-center">
            {"".join([f'<div class="text-center"><p class="text-[8px] text-zinc-500 font-bold">{k}</p><p class="text-lg font-black text-white">{v}</p></div>' for k,v in res['intel'].items()])}
        </div>
    </div>

    <div class="space-y-4 mb-20">
        <h4 class="text-[9px] font-black uppercase text-zinc-600 tracking-widest text-center italic">FORM GUIDE (LAST 5)</h4>
        <div class="flex justify-center gap-10">
            <div class="flex gap-1">{"".join([f'<span class="w-6 h-6 rounded flex items-center justify-center font-black text-[9px] {"bg-green-500 text-black" if f=="W" else "bg-zinc-800 text-zinc-500"}">{f}</span>' for f in res['h_form']])}</div>
            <div class="flex gap-1">{"".join([f'<span class="w-6 h-6 rounded flex items-center justify-center font-black text-[9px] {"bg-green-500 text-black" if f=="W" else "bg-zinc-800 text-zinc-500"}">{f}</span>' for f in res['a_form']])}</div>
        </div>
    </div>
    '''
    return render_template_string(LAYOUT, content=content)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
