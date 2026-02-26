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
        body { font-family: 'Inter', sans-serif; background: #05070a; color: #d4d4d8; }
        .glass { background: rgba(15, 18, 24, 0.8); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.05); }
    </style>
</head>
<body class="p-4 italic">
    <div class="max-w-md mx-auto min-h-screen flex flex-col">
        <header class="flex justify-between items-center py-6 mb-4 border-b border-white/5">
            <h1 class="text-xl font-black tracking-tighter text-white uppercase">PRO<span class="text-green-500">PREDICTOR</span></h1>
            <div class="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
        </header>
        {{ content | safe }}
    </div>
</body>
</html>
"""

@app.route("/")
def hub():
    try:
        # 1. Fetch upcoming events
        events = match_predictor.get_data("events/", {"status": "NS"})
        
        # 2. Critical Check: Ensure events is a valid list
        if not isinstance(events, list) or len(events) == 0:
            return render_template_string(LAYOUT, content='''
                <div class="flex-grow flex flex-col items-center justify-center py-20 text-center">
                    <p class="text-[10px] font-black uppercase tracking-[0.3em] opacity-30">No Fixtures Available</p>
                    <p class="text-[8px] mt-2 text-zinc-600">Check Bzzoiro API Status or Token</p>
                </div>
            ''')
        
        idx = int(request.args.get('i', 0))
        # Ensure index stays within bounds
        idx = max(0, min(idx, len(events) - 1))
        
        m = events[idx]
        analysis = match_predictor.get_structured_analysis(m['id'])
        
        # If no prediction data, don't crash, just show match info with a "Pending" tag
        if "error" in analysis:
            return render_template_string(LAYOUT, content=f'''
                <div class="glass p-8 rounded-[2rem] text-center">
                    <p class="text-white font-black uppercase mb-4">{m.get('home_team', {}).get('name')} vs {m.get('away_team', {}).get('name')}</p>
                    <p class="text-[9px] text-zinc-500 uppercase">AI Analysis Synchronizing...</p>
                    <a href="/?i={idx+1}" class="mt-6 inline-block bg-white text-black px-6 py-2 rounded-full text-[10px] font-black uppercase">Skip Match</a>
                </div>
            ''')

        # Full match display (Master Prompt Layout)
        content = f'''
        <div class="flex justify-between items-center mb-6">
            <span class="text-[10px] font-black text-zinc-600 uppercase tracking-widest">{analysis.get('league', 'International')}</span>
            <span class="text-[9px] font-black text-white bg-zinc-900 px-2 py-1 rounded-md">{analysis.get('time', '00:00')[11:16]}</span>
        </div>
        <div class="text-center mb-8">
            <span class="px-5 py-1.5 rounded-full bg-green-500/10 text-green-500 text-[9px] font-black uppercase tracking-[0.2em] border border-green-500/20">{analysis['tag']}</span>
        </div>
        <div class="glass p-6 rounded-[2.5rem] mb-10 shadow-2xl">
            <span class="text-[9px] font-black text-zinc-600 uppercase block mb-2">🔵 Recommended</span>
            <h2 class="text-2xl font-black text-white uppercase mb-4">{analysis['rec']['t']}</h2>
            <p class="text-4xl font-black text-green-500 italic">+{analysis['rec']['p']}%</p>
        </div>
        <div class="mt-auto flex gap-3 pb-8">
            <a href="/?i={idx-1}" class="w-1/3 glass py-5 rounded-3xl text-center text-[10px] font-black uppercase text-zinc-500">Prev</a>
            <a href="/?i={idx+1}" class="w-2/3 bg-white text-black py-5 rounded-3xl text-center text-[10px] font-black uppercase shadow-xl">Next</a>
        </div>
        '''
        return render_template_string(LAYOUT, content=content)

    except Exception as e:
        # This catches the error and shows it on screen instead of a 500 error
        return render_template_string(LAYOUT, content=f'<div class="p-6 glass rounded-2xl text-red-500 text-[10px] font-mono">CRITICAL ERROR: {str(e)}</div>')

@app.route("/acca")
def acca():
    return render_template_string(LAYOUT, content='<div class="text-center py-20 uppercase font-black opacity-20">ACCA Builder Offline</div>')

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
