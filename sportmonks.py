"""
sportmonks.py -- God Mode API Client
Fetches the "Super Packet" for every match.
"""
import os, json, requests
from datetime import datetime, timezone, timedelta
import database

# YOUR NEW TOKEN
TOKEN = "EbRqkfYJgeCOtHzoC1AXpk1OO4semN0DtJ1P84zrYVNRCT1x4dHVsP9FGJAVL"
BASE  = "https://api.sportmonks.com/v3/football"

# In-memory cache to prevent API spamming
_mem = {}

def _get(endpoint, params=None, cache_hours=4):
    """Smart Fetcher: Checks Memory -> API."""
    p = params or {}
    # Create a unique key for this request
    key = f"sm_{endpoint}_{json.dumps(sorted(p.items()))}"
    
    # 1. Memory Check
    if key in _mem:
        data, ts = _mem[key]
        if (datetime.now() - ts).total_seconds() < cache_hours * 3600:
            return data

    # 2. API Call
    try:
        r = requests.get(f"{BASE}{endpoint}", headers={"Authorization": TOKEN}, params=p, timeout=20)
        if r.status_code == 200:
            res = r.json()
            data = res.get("data")
            # Save to memory
            _mem[key] = (data, datetime.now())
            return data
        else:
            print(f"[API Error] {endpoint}: {r.status_code}")
    except Exception as e:
        print(f"[API Failed] {endpoint}: {e}")
    return None

# ─── CORE ENDPOINTS ──────────────────────────────────────────────────────────

def get_fixtures_today():
    """Get all matches for today with basic details."""
    today = datetime.now().strftime("%Y-%m-%d")
    return _get(f"/fixtures/date/{today}", 
        {"include": "league;participants;scores;state"}, 
        cache_hours=0.5) or []

def get_fixtures_window(days=3):
    """Get fixtures for the next few days."""
    start = datetime.now().strftime("%Y-%m-%d")
    end = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
    return _get(f"/fixtures/between/{start}/{end}", 
        {"include": "league;participants;scores;state"}, 
        cache_hours=1) or []

def get_livescores():
    """Get live matches."""
    return _get("/livescores", 
        {"include": "league;participants;scores;state;events"}, 
        cache_hours=0.01) or []

def get_match_details(fixture_id):
    """
    The 'God Mode' Data Packet. 
    Fetches: Stats, Lineups, H2H, Standings, Odds, Predictions.
    """
    # 1. Basic Match Data with Includes
    # We ask Sportmonks to attach odds and predictions to the fixture to save calls
    match = _get(f"/fixtures/{fixture_id}", 
        {"include": "league;participants;scores;statistics.type;lineups.player;odds.market;predictions"})
    
    if not match: return None
    
    # Extract IDs for H2H
    h_id = next((p['id'] for p in match.get('participants',[]) if p['meta']['location']=='home'), None)
    a_id = next((p['id'] for p in match.get('participants',[]) if p['meta']['location']=='away'), None)
    
    # 2. H2H History (Critical for Intelligence)
    h2h = []
    if h_id and a_id:
        h2h_data = _get(f"/fixtures/head-to-head/{h_id}/{a_id}", {"include": "scores"})
        if h2h_data:
            h2h = h2h_data[:5] # Last 5 meetings only

    # 3. Value Bets (The "Sniper" Data)
    value_bets = _get(f"/predictions/value-bets/fixtures/{fixture_id}") or []

    return {
        "match": match,
        "h2h": h2h,
        "value_bets": value_bets,
        "stats": match.get("statistics", []),
        "predictions": match.get("predictions", []),
        "odds": match.get("odds", [])
    }

# ─── HELPER EXTRACTORS ───────────────────────────────────────────────────────

def extract_teams(fx):
    h = next((p for p in fx.get('participants',[]) if p['meta']['location']=='home'), {})
    a = next((p for p in fx.get('participants',[]) if p['meta']['location']=='away'), {})
    return h.get('id'), h.get('name'), a.get('id'), a.get('name')

def extract_score(fx):
    scores = fx.get('scores', [])
    h_score = next((s['score']['goals'] for s in scores if s['description']=='CURRENT' and s['score']['participant']=='home'), None)
    a_score = next((s['score']['goals'] for s in scores if s['description']=='CURRENT' and s['score']['participant']=='away'), None)
    return h_score, a_score

def extract_state(fx):
    state = fx.get('state', {})
    return state.get('short_name') or state.get('state') or "NS"
