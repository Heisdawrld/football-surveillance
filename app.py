from flask import Flask, render_template_string, request
import match_predictor
import os

app = Flask(__name__)

THEME = """
<script src="https://cdn.tailwindcss.com"></script>
<body class="bg-[#05070a] text-zinc-300 font-sans italic p-4">
    <div class="max-w-md mx-auto min-h-screen flex flex-col">
        <header class="flex justify-between items-center py-6 mb-6">
            <h1 class="text-xl font-black text-white italic tracking-tighter uppercase">PRO<span class="text-green-500">PREDICTOR</span></h1>
            <a href="/acca" class="bg-green-500/10 text-green-500 px-3 py-1.5 rounded-full text-[9px] font-black uppercase border border-green-500/20">ACCA Hub</a>
        </header>
        {{ content | safe }}
    </div>
</body>
"""

@app.route("/")
def index():
    return render_template_string(THEME, content='<a href="/acca" class="block bg-white text-black p-6 rounded-3xl text-center font-black">Check ACCA Builder</a>')

@app.route("/acca")
def acca():
    all_matches = match_predictor.get_all_fixtures()
    all_preds = match_predictor.get_bzzoiro_predictions()
    
    analyzed_pool = []
    for f in all_matches[:20]:
        res = match_predictor.get_match_analysis(
            f['homeTeam']['name'], f['awayTeam']['name'], f['competition']['name'], all_preds
        )
        analyzed_pool.append({
            "match": f"{f['homeTeam']['name']} v {f['awayTeam']['name']}",
            "tip": res['rec']['t'], "odds": res['rec']['o'], "edge": res['rec']['e'], "league": f['competition']['name']
        })

    optimized_pool = sorted(analyzed_pool, key=lambda x: x['edge'], reverse=True)
    
    # Diversified Selection
    acca_selections = []
    curr_odds = 1.0
    used_leagues = set()
    for s in optimized_pool:
        if s['league'] not in used_leagues:
            acca_selections.append(s)
            curr_odds *= s['odds']
            used_leagues.add(s['league'])
            if curr_odds >= 5.0: break

    # RENDER CONTENT
    if not analyzed_pool:
        content = '<div class="py-20 text-center opacity-30 font-black uppercase text-xs">No Data Available for selected range</div>'
    else:
        picks_html = "".join([f'<div class="p-4 bg-white/5 rounded-2xl mb-2 flex justify-between"><span>{s["match"]}</span><span class="text-green-500">{s["odds"]}</span></div>' for s in acca_selections])
        content = f'<div class="text-center"><h2 class="text-white font-black mb-10">DAILY OPTIMIZER</h2>{picks_html}</div>'

    # DEBUG BAR (Hidden logic check)
    debug = f'''
    <div class="mt-20 p-4 bg-red-500/5 rounded-xl border border-red-500/10 text-[8px] font-mono text-zinc-700">
        DATA FLOW: Fixtures({len(all_matches)}) | Predictions({len(all_preds)}) | Analyzed({len(analyzed_pool)})
    </div>'''
    
    return render_template_string(THEME, content=content + debug)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
