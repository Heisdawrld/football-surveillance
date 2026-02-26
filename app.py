from flask import Flask, render_template_string, request, redirect, url_for
import match_predictor
import os

app = Flask(__name__)

LAYOUT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
        body { font-family: 'Inter', sans-serif; background: #05070a; color: #d4d4d8; -webkit-font-smoothing: antialiased; }
        .glass { background: rgba(15, 18, 24, 0.8); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.05); }
        .btn-glow { transition: all 0.2s; }
        .btn-glow:active { transform: scale(0.96); opacity: 0.8; }
    </style>
</head>
<body class="p-4 italic">
    <div class="max-w-md mx-auto min-h-screen flex flex-col">
        <header class="flex justify-between items-center py-6 mb-4 border-b border-white/5">
            <h1 class="text-xl font-black tracking-tighter text-white uppercase">PRO<span class="text-green-500">PREDICTOR</span></h1>
            <div class="flex gap-3">
                <a href="/acca" class="text-[9px] font-black bg-white/5 text-zinc-400 px-3 py-1.5 rounded-full uppercase border border-white/5">ACCA</a>
                <div class="w-2 h-2 bg-green-500 rounded-full animate-pulse self-center"></div>
            </div>
        </header>
        {{ content | safe }}
    </div>
</body>
</html>
"""

@app.route("/")
def hub():
    # 1. Fetch upcoming events
    events = match_predictor.get_data("events/", {"status": "NS"})
    
    # 2. FIX: Handle Empty List or None to prevent KeyError
    if not events or len(events) == 0:
        return render_template_string(LAYOUT, content='''
            <div class="flex-grow flex flex-col items-center justify-center py-20 opacity-30 text-center">
                <div class="w-12 h-12 border-2 border-zinc-800 border-t-green-500 rounded-full animate-spin mb-6"></div>
                <p class="text-[10px] font-black uppercase tracking-[0.3em]">Stream Offline</p>
                <p class="text-[8px] mt-2">No upcoming Bzzoiro fixtures detected</p>
            </div>
        ''')
    
    idx = int(request.args.get('i', 0))
    if idx < 0: idx = 0
    if idx >= len(events): idx = 0
    
    # Safely get the match
    m = events[idx]
    analysis = match_predictor.get_structured_analysis(m['id'])
    
    if "error" in analysis:
        # If no prediction data for this match, skip to next
        if len(events) > 1 and idx < len(events) - 1:
            return redirect(url_for('hub', i=idx+1))
        else:
            return render_template_string(LAYOUT, content='<div class="text-center py-20 font-black uppercase opacity-20 text-[10px]">Processing AI Data...</div>')

    content = f'''
    <div class="flex justify-between items-center mb-6">
        <span class="text-[10px] font-black text-zinc-600 uppercase tracking-widest">{analysis['league']}</span>
        <span class="text-[9px] font-black text-white bg-zinc-900 border border-white/10 px-2 py-1 rounded-md">{analysis['time'][11:16]}</span>
    </div>

    <div class="flex justify-between items-center mb-10 px-4">
        <div class="text-center w-1/3">
            <div class="w-16 h-16 glass rounded-2xl mx-auto mb-3 flex items-center justify-center text-2xl font-black text-white shadow-xl">{analysis['event']['home_team']['name'][0]}</div>
            <p class="text-[10px] font-black uppercase text-zinc-300 leading-tight">{analysis['event']['home_team']['name']}</p>
        </div>
        <div class="text-xl font-black text-zinc-800 italic opacity-40 uppercase">vs</div>
        <div class="text-center w-1/3">
            <div class="w-16 h-16 glass rounded-2xl mx-auto mb-3 flex items-center justify-center text-2xl font-black text-white shadow-xl">{analysis['event']['away_team']['name'][0]}</div>
            <p class="text-[10px] font-black uppercase text-zinc-300 leading-tight">{analysis['event']['away_team']['name']}</p>
        </div>
    </div>

    <div class="text-center mb-8">
        <span class="px-5 py-1.5 rounded-full bg-green-500/10 text-green-500 text-[9px] font-black uppercase tracking-[0.2em] border border-green-500/20">{analysis['tag']}</span>
    </div>

    <div class="glass p-6 rounded-[2.5rem] mb-4 shadow-2xl border-t border-white/10">
        <div class="flex justify-between items-start mb-2">
            <span class="text-[9px] font-black text-zinc-600 uppercase tracking-widest">🔵 Recommended Tip</span>
            <span class="text-3xl font-black text-green-500 italic">+{analysis['rec']['p']}%</span>
        </div>
        <h2 class="text-2xl font-black text-white uppercase tracking-tighter mb-4 leading-tight">{analysis['rec']['t']}</h2>
        <div class="flex items-center gap-2 mb-6">
             <span class="text-zinc-600 text-[9px] font-bold uppercase tracking-widest">Market Value:</span>
             <span class="text-white font-black text-sm">{analysis['rec']['o']}</span>
        </div>
        <div class="space-y-2 border-t border-white/5 pt-5">
            {"".join([f'<p class="text-[9px] text-zinc-400 font-bold uppercase flex items-center gap-3"><span class="w-1.5 h-1.5 bg-green-500 rounded-full shadow-[0_0_8px_rgba(34,197,94,0.6)]"></span>{r}</p>' for r in analysis['rec']['r']])}
        </div>
    </div>

    <div class="grid grid-cols-2 gap-3 mb-6">
        <div class="glass p-5 rounded-[2rem] border-l-2 border-blue-500/30">
            <span class="text-[7px] font-black text-zinc-600 uppercase mb-2 block tracking-[0.2em]">🟢 Safest</span>
            <p class="text-[10px] font-black text-white uppercase mb-1">{analysis['alt']['t']}</p>
            <p class="text-lg font-black text-zinc-700">{analysis['alt']['o']}</p>
        </div>
        <div class="glass p-5 rounded-[2rem] border-l-2 border-red-500/30">
            <span class="text-[7px] font-black text-red-500/40 uppercase mb-2 block tracking-[0.2em]">🔴 High Risk</span>
            <p class="text-[10px] font-black text-white uppercase mb-1">{analysis['risk']['t']}</p>
            <p class="text-lg font-black text-zinc-700">{analysis['risk']['o']}</p>
        </div>
    </div>

    <div class="mt-auto flex gap-3 pb-8">
        <a href="/?i={idx-1}" class="w-1/3 glass py-5 rounded-3xl text-center text-[10px] font-black uppercase text-zinc-500 btn-glow">Prev</a>
        <a href="/?i={idx+1}" class="w-2/3 bg-white text-black py-5 rounded-3xl text-center text-[10px] font-black uppercase btn-glow shadow-xl">Next Fixture</a>
    </div>
    '''
    return render_template_string(LAYOUT, content=content)

@app.route("/acca")
def acca():
    content = '<div class="glass p-10 rounded-[3rem] text-center mt-10"><h2 class="text-2xl font-black text-white italic mb-4 uppercase">ACCA BUILDER</h2><p class="text-zinc-600 text-[9px] font-bold uppercase tracking-[0.3em] mb-10">Compiling 5.00 Odds Ticket</p><a href="/" class="inline-block bg-zinc-800 text-white px-8 py-4 rounded-full text-[9px] font-black uppercase">Return to Hub</a></div>'
    return render_template_string(LAYOUT, content=content)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
