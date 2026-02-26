"""
external_data.py — Free external data sources
Uses API-Football (free tier: 100 req/day at api-football.com)
Sign up free at: https://dashboard.api-football.com/register

Set your key as environment variable:
  APIFOOTBALL_KEY=your_key_here

Falls back gracefully if key is missing or quota is hit.
"""

import os
import json
import requests
from datetime import datetime, timezone
import database

APIFOOTBALL_KEY = os.environ.get("APIFOOTBALL_KEY", "")
APIFOOTBALL_BASE = "https://v3.football.api-sports.io"

# Map our league IDs to API-Football league IDs
# (our Bzzoiro ID → API-Football ID)
LEAGUE_ID_MAP = {
    1:  39,   # Premier League
    2:  94,   # Liga Portugal
    3:  140,  # La Liga
    4:  135,  # Serie A
    5:  78,   # Bundesliga
    11: 203,  # Süper Lig
    12: 40,   # Championship
    13: 179,  # Scottish Premiership
    14: 144,  # Belgian Pro League
    18: 253,  # MLS
    20: 262,  # Liga MX
}

def _apifootball_get(endpoint, params):
    """Make a request to API-Football. Returns None if key missing or error."""
    if not APIFOOTBALL_KEY:
        return None
    headers = {
        "x-rapidapi-host": "v3.football.api-sports.io",
        "x-rapidapi-key":  APIFOOTBALL_KEY,
    }
    try:
        r = requests.get(f"{APIFOOTBALL_BASE}{endpoint}",
                         headers=headers, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        if data.get("errors"):
            print(f"[APIFootball] Error: {data['errors']}")
            return None
        return data.get("response", [])
    except Exception as e:
        print(f"[APIFootball] {endpoint} failed: {e}")
        return None

# ─── H2H ─────────────────────────────────────────────────────────────────────

def get_h2h(home_api_id, away_api_id, last=10):
    """
    Fetch last N head-to-head results between two teams.
    home_api_id / away_api_id are the team IDs from Bzzoiro's event.home_team_obj.api_id
    
    Returns list of match dicts or empty list.
    Caches for 24h to preserve free quota.
    """
    cache_key = f"h2h_{min(home_api_id,away_api_id)}_{max(home_api_id,away_api_id)}"
    cached = database.cache_get("h2h_cache", cache_key)
    if cached:
        return json.loads(cached)

    data = _apifootball_get("/fixtures/headtohead", {
        "h2h": f"{home_api_id}-{away_api_id}",
        "last": last,
    })
    if data is None:
        return []

    results = []
    for f in data:
        fixture = f.get("fixture", {})
        teams   = f.get("teams", {})
        goals   = f.get("goals", {})
        results.append({
            "date":      fixture.get("date", "")[:10],
            "home":      teams.get("home", {}).get("name", "?"),
            "away":      teams.get("away", {}).get("name", "?"),
            "home_goal": goals.get("home"),
            "away_goal": goals.get("away"),
            "status":    fixture.get("status", {}).get("short", ""),
        })

    database.cache_set("h2h_cache", cache_key, json.dumps(results))
    return results

def summarise_h2h(h2h_list, home_team_name):
    """
    Summarise H2H data into stats useful for the prediction model.
    home_team_name: the home team in today's match (for W/D/L calculation)
    """
    if not h2h_list:
        return None

    finished = [m for m in h2h_list if m.get("status") == "FT"]
    if not finished:
        return None

    total      = len(finished)
    home_wins  = 0
    draws      = 0
    away_wins  = 0
    total_goals = 0
    over_25    = 0
    btts       = 0

    for m in finished:
        hg = m.get("home_goal") or 0
        ag = m.get("away_goal") or 0
        total_goals += hg + ag
        if hg + ag > 2:
            over_25 += 1
        if hg > 0 and ag > 0:
            btts += 1
        # Wins from today's home team perspective
        if m["home"] == home_team_name:
            if hg > ag: home_wins += 1
            elif hg == ag: draws += 1
            else: away_wins += 1
        else:
            if ag > hg: home_wins += 1
            elif hg == ag: draws += 1
            else: away_wins += 1

    return {
        "total":        total,
        "home_wins":    home_wins,
        "draws":        draws,
        "away_wins":    away_wins,
        "avg_goals":    round(total_goals / total, 2),
        "over_25_pct":  round(over_25 / total * 100, 1),
        "btts_pct":     round(btts / total * 100, 1),
        "matches":      finished[:5],  # last 5 for display
    }

# ─── Injuries ────────────────────────────────────────────────────────────────

def get_injuries(team_api_id, league_api_id, season=2025):
    """
    Get current injuries/suspensions for a team.
    Caches for 6h (injuries change more frequently).
    """
    if not team_api_id:
        return []

    cache_key = f"inj_{team_api_id}_{league_api_id}_{season}"
    cached    = database.cache_get("injury_cache", cache_key, max_age_hours=6)
    if cached:
        return json.loads(cached)

    data = _apifootball_get("/injuries", {
        "team":   team_api_id,
        "league": league_api_id,
        "season": season,
    })
    if data is None:
        return []

    injuries = []
    for item in data[:10]:  # cap at 10 per team
        player = item.get("player", {})
        inj    = item.get("injury",  {})
        injuries.append({
            "name":   player.get("name", "?"),
            "type":   inj.get("type",   "Injured"),
            "reason": inj.get("reason", ""),
        })

    database.cache_set("injury_cache", cache_key, json.dumps(injuries))
    return injuries

# ─── Season Stats ────────────────────────────────────────────────────────────

def get_team_season_stats(team_api_id, league_api_id, season=2025):
    """
    Get a team's season statistics from API-Football.
    Caches for 12h.
    """
    if not team_api_id:
        return None

    cache_key = f"stats_{team_api_id}_{league_api_id}_{season}"
    cached    = database.cache_get("h2h_cache", cache_key, max_age_hours=12)
    if cached:
        return json.loads(cached)

    data = _apifootball_get("/teams/statistics", {
        "team":   team_api_id,
        "league": league_api_id,
        "season": season,
    })
    if not data:
        return None

    s = data[0] if isinstance(data, list) else data
    goals_for   = s.get("goals", {}).get("for",     {})
    goals_ag    = s.get("goals", {}).get("against",  {})
    fixtures    = s.get("fixtures", {})
    played      = fixtures.get("played", {}).get("total", 1) or 1

    stats = {
        "played":        played,
        "wins":          fixtures.get("wins",   {}).get("total", 0),
        "draws":         fixtures.get("draws",  {}).get("total", 0),
        "losses":        fixtures.get("loses",  {}).get("total", 0),
        "goals_scored":  goals_for.get("total", {}).get("total", 0),
        "goals_conceded":goals_ag.get("total",  {}).get("total", 0),
        "avg_scored":    round(goals_for.get("average", {}).get("total", 0) or 0, 2),
        "avg_conceded":  round(goals_ag.get("average",  {}).get("total", 0) or 0, 2),
        "clean_sheets":  s.get("clean_sheet", {}).get("total", 0),
        "failed_to_score": s.get("failed_to_score", {}).get("total", 0),
        "biggest_win":   s.get("biggest", {}).get("wins",   {}).get("home", ""),
        "form":          s.get("form", ""),  # e.g. "WWDLW"
    }

    database.cache_set("h2h_cache", cache_key, json.dumps(stats))
    return stats

# ─── Enrich match data ────────────────────────────────────────────────────────

def enrich_match(api_data):
    """
    Take a Bzzoiro match dict and add H2H, injuries, season stats.
    Returns enriched dict. Fails gracefully — never crashes the app.
    """
    enriched = {
        "h2h":           None,
        "h2h_summary":   None,
        "home_injuries": [],
        "away_injuries": [],
        "home_stats":    None,
        "away_stats":    None,
    }

    if not APIFOOTBALL_KEY:
        return enriched  # graceful fallback — show nothing rather than crash

    try:
        event       = api_data.get("event", {})
        league      = event.get("league", {})
        our_l_id    = league.get("id", 0)
        ext_l_id    = LEAGUE_ID_MAP.get(our_l_id)

        home_obj    = event.get("home_team_obj", {})
        away_obj    = event.get("away_team_obj", {})
        home_ext_id = home_obj.get("api_id")
        away_ext_id = away_obj.get("api_id")
        home_name   = event.get("home_team", "")

        if home_ext_id and away_ext_id:
            h2h_raw  = get_h2h(home_ext_id, away_ext_id)
            h2h_sum  = summarise_h2h(h2h_raw, home_name)
            enriched["h2h"]         = h2h_raw
            enriched["h2h_summary"] = h2h_sum

        if ext_l_id:
            enriched["home_injuries"] = get_injuries(home_ext_id, ext_l_id)
            enriched["away_injuries"] = get_injuries(away_ext_id, ext_l_id)
            enriched["home_stats"]    = get_team_season_stats(home_ext_id, ext_l_id)
            enriched["away_stats"]    = get_team_season_stats(away_ext_id, ext_l_id)

    except Exception as e:
        print(f"[enrich_match] error: {e}")

    return enriched
