# ... (Keep Imports and get_badge function)

@app.route("/match")
def match():
    res = get_match_analysis(request.args.get("id"))
    if "error" in res: return render_template_string(LAYOUT, content='<p class="text-center mt-20">Sync Error</p>')
    
    # Generate the Points/Rank table rows
    stats_html = ""
    for s in res['stats']:
        stats_html += f'''
        <div class="flex justify-between items-center py-3 border-b border-white/5 text-[10px] font-bold italic">
            <span class="w-1/3 text-left text-white uppercase">{s['h']}</span>
            <span class="w-1/3 text-center text-zinc-600 uppercase tracking-widest">{s['label']}</span>
            <span class="w-1/3 text-right text-white uppercase">{s['a']}</span>
        </div>'''

    content = f'''
    <div class="mb-6"><a href="/" class="text-zinc-600 font-bold text-[10px] uppercase">← RETURN</a></div>
    
    <div class="flex justify-center items-center gap-6 mb-10">
        <div class="text-center"><img src="{get_badge(res['h_name'])}" class="w-14 h-14 rounded-full border border-white/10 mb-2"><p class="text-[8px] font-black text-zinc-500 uppercase">{res['h_name']}</p></div>
        <div class="text-zinc-800 font-black italic text-xl italic">VS</div>
        <div class="text-center"><img src="{get_badge(res['a_name'])}" class="w-14 h-14 rounded-full border border-white/10 mb-2"><p class="text-[8px] font-black text-zinc-500 uppercase">{res['a_name']}</p></div>
    </div>

    <div class="bg-[#10141d] p-8 rounded-[2rem] border border-white/5 mb-6 text-center relative overflow-hidden">
        <div class="absolute top-0 right-0 p-3 text-green-500/20 font-black italic text-[8px] tracking-widest">{res['tag']}</div>
        <span class="text-[9px] font-black uppercase text-zinc-500 mb-2 block tracking-widest italic">AI ANALYSIS</span>
        <h2 class="text-3xl font-black text-white italic uppercase tracking-tighter mb-1 leading-none">{res['best_tip']['t']}</h2>
        <p class="text-5xl font-black text-green-500 italic tracking-tighter">{res['best_tip']['p']:.0f}% <span class="text-[10px] text-zinc-600">CONF</span></p>
    </div>

    <div class="grid grid-cols-2 gap-4 mb-6 text-center">
        <div class="bg-[#0f1218] p-5 rounded-2xl border border-white/5"><span class="text-[8px] text-zinc-500 font-black uppercase block mb-1">SAFE SHIELD</span><span class="text-xs font-black text-white italic">{res['safer']}</span></div>
        <div class="bg-[#0f1218] p-5 rounded-2xl border border-white/5"><span class="text-[8px] text-zinc-500 font-black uppercase block mb-1">HIGH VALUE</span><span class="text-xs font-black text-red-500 italic">{res['risky']}</span></div>
    </div>

    <div class="bg-black/20 p-6 rounded-2xl border border-white/5 mb-8">
        <h4 class="text-[9px] font-black uppercase text-zinc-600 mb-4 tracking-widest text-center italic text-center underline decoration-zinc-800">MARKET PROBABILITIES</h4>
        <div class="flex justify-around items-center">
            {"".join([f'<div class="text-center"><p class="text-[8px] text-zinc-500 font-bold mb-1">{k}</p><p class="text-lg font-black text-white">{v}</p></div>' for k,v in res['intel'].items()])}
        </div>
    </div>

    <div class="mb-10 text-center">
        <h4 class="text-[9px] font-black uppercase text-zinc-600 mb-4 tracking-widest italic text-center underline decoration-zinc-800">TABLE ANALYSIS</h4>
        <div class="bg-[#0f1218] p-6 rounded-2xl border border-white/5 mb-4">{stats_html}</div>
        <div class="flex justify-center gap-10 opacity-60 mt-6">
            <div class="flex gap-1">{"".join([f'<span class="w-5 h-5 rounded flex items-center justify-center font-black text-[8px] {"bg-green-500 text-black" if f=="W" else "bg-red-500/20 text-red-500" if f=="L" else "bg-zinc-800 text-zinc-500"}">{f}</span>' for f in res['h_form']])}</div>
            <div class="flex gap-1">{"".join([f'<span class="w-5 h-5 rounded flex items-center justify-center font-black text-[8px] {"bg-green-500 text-black" if f=="W" else "bg-red-500/20 text-red-500" if f=="L" else "bg-zinc-800 text-zinc-500"}">{f}</span>' for f in res['a_form']])}</div>
        </div>
    </div>
    '''
    return render_template_string(LAYOUT, content=content)
