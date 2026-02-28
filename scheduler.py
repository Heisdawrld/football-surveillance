@app.route("/match/<int:match_id>")
def match_page(match_id):
    try:
        # 1. FETCH GOD MODE DATA
        data = sportmonks.get_match_details(match_id)
        if not data:
            return render_template_string(LAYOUT, content='<div class="empty">Match data unavailable. API limit or ID error.</div>', page="match")
            
        # 2. RUN BRAIN
        analysis = match_predictor.analyze_match(data)
        if not analysis:
            return render_template_string(LAYOUT, content='<div class="empty">Not enough data to generate Smart Prediction.</div>', page="match")

        tips = analysis['tips']
        rec = tips.get('recommended') or {"selection": "--", "prob": 0, "odds": 0}
        safe = tips.get('safest') or {"selection": "--", "prob": 0, "odds": 0}
        risky = tips.get('risky') or {"selection": "--", "prob": 0, "odds": 0}

        # 3. RENDER UI
        # (I am injecting the values directly into your existing high-end HTML structure)
        
        content = f'''
        <div class="match-hero up">
            <div class="match-league">PREMIER LEAGUE</div> <div class="match-teams">
                <div class="team-block"><div class="team-name">{analysis['teams']['home']}</div></div>
                <div class="vs-block"><div class="vs-sep">VS</div></div>
                <div class="team-block"><div class="team-name">Away</div></div>
            </div>
        </div>

        <div class="pred-card reliable up d1">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px">
                <div>
                    <div style="font-size:.52rem;font-weight:700;letter-spacing:2.5px;text-transform:uppercase;color:var(--t2);margin-bottom:5px">⚡ RECOMMENDED (VALUE)</div>
                    <div class="tip-main" style="color:var(--g)">{rec['selection']}</div>
                    <div class="tip-prob">{rec['prob']}% Prob &middot; Odds <span style="color:var(--gold)">{rec['odds']}</span></div>
                </div>
                <span class="badge bg-green">VALUE</span>
            </div>
            <div class="tip-reason">{analysis['analysis']}</div>
        </div>

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:7px;margin-bottom:8px" class="up d2">
            
            <div class="card" style="margin:0;border-color:rgba(79,142,247,.25);background:linear-gradient(135deg,rgba(79,142,247,.07),transparent)">
                <div class="card-title">🛡️ BANKER</div>
                <div style="font-size:.9rem;font-weight:900;color:var(--b);line-height:1.2">{safe['selection']}</div>
                <div style="font-size:.62rem;color:var(--t2);margin-top:3px">{safe['prob']}% &middot; {safe['odds']}</div>
            </div>

            <div class="card" style="margin:0;border-color:rgba(255,69,58,.25);background:linear-gradient(135deg,rgba(255,69,58,.07),transparent)">
                <div class="card-title">💣 HIGH REWARD</div>
                <div style="font-size:.9rem;font-weight:900;color:var(--r);line-height:1.2">{risky['selection']}</div>
                <div style="font-size:.62rem;color:var(--t2);margin-top:3px">{risky['prob']}% &middot; {risky['odds']}</div>
            </div>
        </div>
        '''

        return render_template_string(LAYOUT, content=content, page="match")

    except Exception as e:
        import traceback; traceback.print_exc()
        return render_template_string(LAYOUT, content=f'<div class="empty">System Error: {str(e)}</div>', page="match")
