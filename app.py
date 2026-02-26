from flask import Flask, render_template_string, request, redirect, url_for
import match_predictor
from datetime import datetime, timedelta
import os

app = Flask(__name__)

# PREMIUM MOBILE APP CSS
CSS = """
<script src="https://cdn.tailwindcss.com"></script>
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
    body { font-family: 'Inter', sans-serif; background: #05070a; color: #d4d4d8; -webkit-tap-highlight-color: transparent; }
    .glass { background: rgba(15, 18, 24, 0.8); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.05); }
    .safe-area { padding-bottom: env(safe-area-inset-bottom); }
    .nav-btn:active { transform: scale(0.95); transition: 0.1s; }
</style>
"""

# 🏠 1. LANDING PAGE
@app.route("/")
def index():
    content = f'''
    {CSS}
    <div class="max-w-md mx-auto min-h-screen p-6 flex flex-col justify-center">
        <div class="mb-10">
            <h1 class="text-4xl font-black text-white italic tracking-tighter uppercase mb-2">PRO<span class="text-green-500">PREDICTOR</span></h1>
            <p class="text-zinc-500 text-xs font-bold uppercase tracking-widest leading-loose">Advanced Football Analysis & <br>Structured Betting Intelligence.</p>
        </div>
        
        <div class="space-y-4 mb-20">
            <div class="glass p-4 rounded-2xl flex items-center gap-4">
                <div class="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
                <span class="text-[10px] font-black uppercase italic">Recommended Value Tips</span>
            </div>
            <div class="glass p-4 rounded-2xl flex items-center gap-4">
                <div class="w-2 h-2 bg-green-500 rounded-full"></div>
                <span class="text-[10px] font-black uppercase italic">Safest High-Probability Markets</span>
            </div>
        </div>

        <a href="/leagues" class="bg-white text-black py-5 rounded-3xl text-center font-black uppercase text-xs tracking-widest nav-btn shadow-[0_20px_40px_rgba(255,255,255,0.1)]">Enter Intelligence Hub</a>
    </div>
    '''
    return render_template_string(content)

# 🌍 2. LEAGUES SECTION
@app.route("/leagues")
def leagues():
    league_list = [
        {"id": "PL", "n": "Premier League", "c": "England"},
        {"id": "PD", "n": "La Liga", "c": "Spain"},
        {"id": "SA", "n": "Serie A", "c": "Italy"},
        {"id": "BL1", "n": "Bundesliga", "c": "Germany"},
        {"id": "FL1", "n": "Ligue 1", "c": "France"}
    ]
    
    cards = "".join([f'''
    <a href="/fixtures?league={l['id']}" class="glass p-6 rounded-[2rem] flex flex-col items-center justify-center text-center gap-3 nav-btn">
        <div class="w-12 h-12 bg-white/5 rounded-full flex items-center justify-center font-black text-white italic">{l['id']}</div>
        <p class="text-[10px] font-black uppercase text-zinc-400 leading-tight">{l['n']}</p>
    </a>''' for l in league_list])

    content = f'''
    {CSS}
    <div class="max-w-md mx-auto p-6">
        <header class="flex justify-between items-center mb-10">
            <h2 class="text-xl font-black text-white italic uppercase tracking-tighter">Select <span class="text-green-500">League</span></h2>
            <a href="/acca" class="bg-green-500/10 text-green-500 px-3 py-1.5 rounded-full text-[9px] font-black uppercase">ACCA Builder</a>
        </header>
        <div class="grid grid-cols-2 gap-4">{cards}</div>
    </div>
    '''
    return render_template_string(content)

# 📅 3. FIXTURE LIST (LEAGUE-SPECIFIC)
@app.route("/fixtures")
def fixtures():
    league_id = request.args.get('league')
    all_m = match_predictor.get_all_fixtures()
    matches = [m for m in all_m if m['competition']['code'] == league_id]
    
    # Simple Date Grouping
    today = datetime.now().strftime('%Y-%m-%d')
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    
    table_rows = ""
    for m in matches:
        match_time = m['utcDate'][11:16]
        # Adding 1 hour for WAT (Nigeria)
        hour = int(match_time[:2]) + 1
        wat_time = f"{hour:02d}:{match_time[3:]}"
        
        table_rows += f'''
        <a href="/analysis?h={m['homeTeam']['name']}&a={m['awayTeam']['name']}&l={league_id}&t={wat_time}" class="flex items-center justify-between p-5 bg-white/5 rounded-2xl mb-2 border border-white/5 nav-btn">
            <span class="text-[10px] font-black text-zinc-600 w-12">{wat_time}</span>
            <div class="flex-grow flex justify-center gap-3 text-[10px] font-black text-white uppercase italic truncate">
                <span>{m['homeTeam']['name']}</span>
                <span class="opacity-20">vs</span>
                <span>{m['awayTeam']['name']}</span>
            </div>
            <span class="text-green-500 text-[10px] font-black ml-4">→</span>
        </a>'''

    content = f'''
    {CSS}
    <div class="max-w-md mx-auto p-6">
        <a href="/leagues" class="text-zinc-600 text-[10px] font-black uppercase tracking-widest mb-6 block">← Back to Leagues</a>
        <h3 class="text-zinc-500 text-[9px] font-black uppercase tracking-[0.4em] mb-6">Upcoming Fixtures (WAT)</h3>
        <div class="space-y-4">
            <div class="text-white text-[10px] font-black uppercase mb-4 opacity-30 italic">Match Schedule</div>
            {table_rows if table_rows else '<p class="text-center opacity-20 py-10 uppercase font-black">No Fixtures Scheduled</p>'}
        </div>
    </div>
    '''
    return render_template_string(content)

# 📊 4. MATCH ANALYSIS PAGE
@app.route("/analysis")
def analysis():
    h, a = request.args.get('h'), request.args.get('a')
    wat_time = request.args.get('t')
    res = match_predictor.get_match_analysis(h, a)
    
    content = f'''
    {CSS}
    <div class="max-w-md mx-auto p-6">
        <header class="flex justify-between items-center mb-8">
            <a href="javascript:history.back()" class="text-zinc-600 text-[9px] font-black uppercase italic">← Fixtures</a>
            <span class="bg-zinc-900 border border-white/10 px-3 py-1 rounded text-[9px] font-black text-white tracking-tighter">{wat_time} WAT</span>
        </header>

        <div class="flex justify-between items-center mb-10 text-center">
            <div class="w-1/3"><div class="w-14 h-14 glass rounded-2xl mx-auto mb-2 flex items-center justify-center text-xl font-black text-white italic">{h[0]}</div><p class="text-[9px] font-black uppercase text-zinc-400">{h}</p></div>
            <div class="text-xl font-black text-zinc-800 opacity-30 italic uppercase">VS</div>
            <div class="w-1/3"><div class="w-14 h-14 glass rounded-2xl mx-auto mb-2 flex items-center justify-center text-xl font-black text-white italic">{a[0]}</div><p class="text-[9px] font-black uppercase text-zinc-400">{a}</p></div>
        </div>

        <div class="text-center mb-8"><span class="px-5 py-1.5 rounded-full bg-green-500/10 text-green-500 text-[9px] font-black uppercase tracking-[0.2em] border border-green-500/20">{res['tag']}</span></div>

        <div class="glass p-6 rounded-[2.5rem] mb-4 shadow-2xl relative border-t border-white/10 italic">
            <span class="text-[9px] font-black text-zinc-600 uppercase tracking-widest mb-4 block">🔵 Recommended Tip</span>
            <h2 class="text-3xl font-black text-white uppercase tracking-tighter mb-4 leading-none">{res['rec']['t']}</h2>
            <div class="flex items-center justify-between mb-6">
                <span class="text-3xl font-black text-green-500 tracking-tighter">+{res['rec']['p']}%</span>
                <span class="text-white font-black text-sm bg-white/5 px-3 py-1 rounded-lg">ODDS: {res['rec']['o']}</span>
            </div>
            <div class="space-y-2 border-t border-white/5 pt-5 uppercase">
                {"".join([f'<p class="text-[9px] text-zinc-500 font-bold flex items-center gap-3"><span class="w-1.5 h-1.5 bg-green-500 rounded-full shadow-[0_0_8px_rgba(34,197,94,0.6)]"></span>{r}</p>' for r in res['rec']['r']])}
            </div>
        </div>

        <div class="glass p-6 rounded-[2.5rem] mt-10 italic">
             <h3 class="text-[8px] font-black text-zinc-700 uppercase tracking-[0.4em] mb-6 text-center underline decoration-zinc-800">Match Insights & Form</h3>
             <div class="space-y-4">
                <div class="flex justify-between items-center text-[10px] font-black uppercase tracking-widest">
                    <span class="text-zinc-500 italic">{h} Form</span>
                    <div class="flex gap-1">{"".join([f'<span class="w-4 h-4 rounded-sm flex items-center justify-center {"bg-green-500 text-black" if f=="W" else "bg-zinc-800 text-zinc-600"}">{f}</span>' for f in res['form']['h']])}</div>
                </div>
                <div class="flex justify-between items-center text-[10px] font-black uppercase tracking-widest">
                    <span class="text-zinc-500 italic">Volatility</span>
                    <span class="text-yellow-500">{res['stats']['vol']}</span>
                </div>
             </div>
        </div>
    </div>
    '''
    return render_template_string(content)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
