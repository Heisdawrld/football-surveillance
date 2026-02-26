"""
external_data.py — API Football Integration
Real H2H, team form, injuries, season stats, standings
API key: APIFOOTBALL_KEY environment variable
"""

import os, json, requests
from datetime import datetime, timezone
import database

APIFOOTBALL_KEY  = os.environ.get("APIFOOTBALL_KEY", "d1d7aaea599eb42ce6a723c2935ee70e")
APIFOOTBALL_BASE = "https://v3.football.api-sports.io"
CURRENT_SEASON   = 2025

LEAGUE_ID_MAP = {
    1: 39, 2: 94, 3: 140, 4: 135, 5: 78, 11: 203,
    12: 40, 13: 179, 14: 144, 18: 253, 20: 262, 22: 172, 23: 283,
}

def _get(endpoint, params):
    if not APIFOOTBALL_KEY:
        return None
    headers = {
        "x-rapidapi-key":  APIFOOTBALL_KEY,
        "x-rapidapi-host": "v3.football.api-sports.io",
    }
    try:
        r = requests.get(f"{APIFOOTBALL_BASE}{endpoint}", headers=headers,
                         params=params, timeout=12)
        r.raise_for_status()
        data = r.json()
        if data.get("errors"):
            print(f"[APIFootball] {endpoint}: {data['errors']}")
            return None
        return data.get("response", [])
    except Exception as e:
        print(f"[APIFootball] {endpoint} failed: {e}")
        return None

def get_h2h(home_api_id, away_api_id, last=8):
    if not home_api_id or not away_api_id:
        return []
    cache_key = f"h2h_{min(home_api_id,away_api_id)}_{max(home_api_id,away_api_id)}"
    cached = database.cache_get("h2h_cache", cache_key)
    if cached:
        return json.loads(cached)
    data = _get("/fixtures/headtohead", {
        "h2h": f"{home_api_id}-{away_api_id}", "last": last, "status": "FT"
    })
    if not data:
        return []
    results = []
    for f in data:
        fix = f.get("fixture", {}); teams = f.get("teams", {})
        goals = f.get("goals", {}); score = f.get("score", {})
        ht = score.get("halftime", {})
        results.append({
            "date": fix.get("date","")[:10],
            "home": teams.get("home",{}).get("name","?"),
            "away": teams.get("away",{}).get("name","?"),
            "home_goals": goals.get("home"),
            "away_goals": goals.get("away"),
            "ht_home": ht.get("home"), "ht_away": ht.get("away"),
            "status": fix.get("status",{}).get("short",""),
        })
    database.cache_set("h2h_cache", cache_key, json.dumps(results))
    return results

def summarise_h2h(h2h_list, home_name, away_name):
    if not h2h_list:
        return None
    finished = [m for m in h2h_list if m.get("status")=="FT" and m.get("home_goals") is not None]
    if not finished:
        return None
    hw = dr = aw = tg = o15 = o25 = btts_c = 0
    for m in finished:
        hg = m["home_goals"] or 0; ag = m["away_goals"] or 0
        tg += hg + ag
        if hg + ag > 1: o15 += 1
        if hg + ag > 2: o25 += 1
        if hg > 0 and ag > 0: btts_c += 1
        if m["home"] == home_name:
            if hg > ag: hw += 1
            elif hg == ag: dr += 1
            else: aw += 1
        else:
            if ag > hg: hw += 1
            elif hg == ag: dr += 1
            else: aw += 1
    n = len(finished)
    return {
        "total": n, "home_wins": hw, "draws": dr, "away_wins": aw,
        "avg_goals": round(tg/n, 2),
        "over_15_pct": round(o15/n*100, 1),
        "over_25_pct": round(o25/n*100, 1),
        "btts_pct": round(btts_c/n*100, 1),
        "matches": finished,
    }

def get_last_matches(team_api_id, last=5):
    if not team_api_id:
        return []
    cache_key = f"last_{team_api_id}_{last}"
    cached = database.cache_get("h2h_cache", cache_key, max_age_hours=6)
    if cached:
        return json.loads(cached)
    data = _get("/fixtures", {"team": team_api_id, "last": last, "status": "FT"})
    if not data:
        return []
    matches = []
    for f in data:
        fix = f.get("fixture",{}); teams = f.get("teams",{})
        goals = f.get("goals",{}); lg = f.get("league",{})
        matches.append({
            "date": fix.get("date","")[:10],
            "home": teams.get("home",{}).get("name","?"),
            "away": teams.get("away",{}).get("name","?"),
            "home_goals": goals.get("home"),
            "away_goals": goals.get("away"),
            "league": lg.get("name",""),
        })
    matches.sort(key=lambda x: x["date"], reverse=True)
    database.cache_set("h2h_cache", cache_key, json.dumps(matches))
    return matches

def get_team_form_from_matches(matches, team_name):
    form = []
    for m in matches:
        hg = m.get("home_goals") or 0; ag = m.get("away_goals") or 0
        if m["home"] == team_name:
            form.append("W" if hg>ag else "D" if hg==ag else "L")
        else:
            form.append("W" if ag>hg else "D" if hg==ag else "L")
    return form

def get_injuries(team_api_id, league_api_id):
    if not team_api_id or not league_api_id:
        return []
    cache_key = f"inj_{team_api_id}_{league_api_id}"
    cached = database.cache_get("injury_cache", cache_key, max_age_hours=4)
    if cached:
        return json.loads(cached)
    data = _get("/injuries", {"team": team_api_id, "league": league_api_id, "season": CURRENT_SEASON})
    if not data:
        return []
    injuries = [{"name": i.get("player",{}).get("name","?"),
                 "type": i.get("injury",{}).get("type","Injured"),
                 "reason": i.get("injury",{}).get("reason","")} for i in data[:8]]
    database.cache_set("injury_cache", cache_key, json.dumps(injuries))
    return injuries

def get_team_stats(team_api_id, league_api_id):
    if not team_api_id or not league_api_id:
        return None
    cache_key = f"stats_{team_api_id}_{league_api_id}"
    cached = database.cache_get("h2h_cache", cache_key, max_age_hours=12)
    if cached:
        return json.loads(cached)
    data = _get("/teams/statistics", {"team": team_api_id, "league": league_api_id, "season": CURRENT_SEASON})
    if not data:
        return None
    s = data[0] if isinstance(data, list) else data
    gf = s.get("goals",{}).get("for",{}); ga = s.get("goals",{}).get("against",{})
    fix = s.get("fixtures",{})
    stats = {
        "played":         fix.get("played",{}).get("total",1) or 1,
        "wins":           fix.get("wins",{}).get("total",0),
        "draws":          fix.get("draws",{}).get("total",0),
        "losses":         fix.get("loses",{}).get("total",0),
        "goals_scored":   gf.get("total",{}).get("total",0),
        "goals_conceded": ga.get("total",{}).get("total",0),
        "avg_scored":     float(gf.get("average",{}).get("total",0) or 0),
        "avg_conceded":   float(ga.get("average",{}).get("total",0) or 0),
        "clean_sheets":   s.get("clean_sheet",{}).get("total",0),
        "failed_to_score":s.get("failed_to_score",{}).get("total",0),
        "form":           s.get("form",""),
        "home_wins":      fix.get("wins",{}).get("home",0),
        "away_wins":      fix.get("wins",{}).get("away",0),
    }
    database.cache_set("h2h_cache", cache_key, json.dumps(stats))
    return stats

def get_standings(league_api_id):
    cache_key = f"standings_{league_api_id}"
    cached = database.cache_get("h2h_cache", cache_key, max_age_hours=6)
    if cached:
        return json.loads(cached)
    data = _get("/standings", {"league": league_api_id, "season": CURRENT_SEASON})
    if not data:
        return {}
    table = {}
    try:
        for team in data[0]["league"]["standings"][0]:
            tid = str(team["team"]["id"])
            table[tid] = {
                "rank": team.get("rank",0),
                "name": team["team"]["name"],
                "points": team.get("points",0),
                "played": team.get("all",{}).get("played",0),
                "gd": team.get("goalsDiff",0),
                "form": team.get("form",""),
            }
    except Exception as e:
        print(f"[standings] {e}")
    database.cache_set("h2h_cache", cache_key, json.dumps(table))
    return table

def enrich_match(api_data):
    enriched = {
        "h2h": [], "h2h_summary": None,
        "home_last": [], "away_last": [],
        "home_injuries": [], "away_injuries": [],
        "home_stats": None, "away_stats": None,
        "standings": {}, "has_data": False,
        "home_form": [], "away_form": [],
    }
    if not APIFOOTBALL_KEY:
        return enriched
    try:
        event = api_data.get("event", {})
        league = event.get("league", {})
        our_l_id = league.get("id", 0)
        ext_l_id = LEAGUE_ID_MAP.get(our_l_id)
        home_obj = event.get("home_team_obj", {})
        away_obj = event.get("away_team_obj", {})
        home_ext_id = home_obj.get("api_id")
        away_ext_id = away_obj.get("api_id")
        home_name = event.get("home_team", "")
        away_name = event.get("away_team", "")

        if home_ext_id and away_ext_id:
            enriched["h2h"] = get_h2h(home_ext_id, away_ext_id)
            enriched["h2h_summary"] = summarise_h2h(enriched["h2h"], home_name, away_name)
            enriched["home_last"] = get_last_matches(home_ext_id)
            enriched["away_last"] = get_last_matches(away_ext_id)
            enriched["home_form"] = get_team_form_from_matches(enriched["home_last"], home_name)
            enriched["away_form"] = get_team_form_from_matches(enriched["away_last"], away_name)

        if ext_l_id:
            enriched["home_injuries"] = get_injuries(home_ext_id, ext_l_id)
            enriched["away_injuries"] = get_injuries(away_ext_id, ext_l_id)
            enriched["home_stats"] = get_team_stats(home_ext_id, ext_l_id)
            enriched["away_stats"] = get_team_stats(away_ext_id, ext_l_id)
            enriched["standings"] = get_standings(ext_l_id)

        enriched["has_data"] = bool(
            enriched["h2h"] or enriched["home_last"] or enriched["home_stats"]
        )
    except Exception as e:
        import traceback
        print(f"[enrich_match] {e}\n{traceback.format_exc()}")
    return enriched

def build_analyst_narrative(enriched, h_name, a_name):
    """Real analyst-style 1-line observations from live data."""
    h = h_name.split()[0]; a = a_name.split()[0]
    h_form = enriched.get("home_form", [])
    a_form = enriched.get("away_form", [])
    h2h    = enriched.get("h2h_summary")
    h_st   = enriched.get("home_stats")
    a_st   = enriched.get("away_stats")
    h_inj  = enriched.get("home_injuries", [])
    a_inj  = enriched.get("away_injuries", [])
    out    = {}

    # Form momentum
    if h_form or a_form:
        h_pts = sum(3 if r=="W" else 1 if r=="D" else 0 for r in h_form)
        a_pts = sum(3 if r=="W" else 1 if r=="D" else 0 for r in a_form)
        h_max = max(len(h_form)*3, 1); a_max = max(len(a_form)*3, 1)
        hp = round(h_pts/h_max*100); ap = round(a_pts/a_max*100)
        hs = " ".join(h_form) if h_form else "—"
        as_ = " ".join(a_form) if a_form else "—"
        if hp > ap + 20:
            out["form"] = f"{h} in strong form ({hs}) · {a} struggling ({as_})"
        elif ap > hp + 20:
            out["form"] = f"{a} in-form ({as_}) · {h} poor run ({hs})"
        else:
            out["form"] = f"Evenly matched recent form · {h}: {hs} · {a}: {as_}"
        if hp >= 80:
            out["morale"] = f"{h} full of confidence — {len([r for r in h_form if r=='W'])} wins in last {len(h_form)}"
        elif ap >= 80:
            out["morale"] = f"{a} on a hot streak — {len([r for r in a_form if r=='W'])} wins in last {len(a_form)}"
        else:
            out["morale"] = None

    # H2H
    if h2h and h2h["total"] >= 3:
        hw=h2h["home_wins"]; dr=h2h["draws"]; aw=h2h["away_wins"]; n=h2h["total"]
        if hw/n >= 0.6:
            dom = f"{h} dominant in this fixture ({hw}W-{dr}D-{aw}L)"
        elif aw/n >= 0.6:
            dom = f"{a} historically strong here ({aw}W-{dr}D-{hw}L)"
        elif dr/n >= 0.5:
            dom = f"This fixture draws frequently — {dr} of {n} meetings ended level"
        else:
            dom = f"Tight H2H — {hw}W {dr}D {aw}L over {n} meetings"
        out["h2h"] = f"{dom} · Avg {h2h['avg_goals']} goals"

    # Goal trend
    if h_st and a_st:
        hs_avg = h_st.get("avg_scored",0); hc_avg = h_st.get("avg_conceded",0)
        as_avg = a_st.get("avg_scored",0); ac_avg = a_st.get("avg_conceded",0)
        exp = round((hs_avg + ac_avg + as_avg + hc_avg)/2, 1)
        if exp >= 3.0:
            out["goals"] = f"Both sides open defensively — projected {exp} goals. {h} scores {hs_avg}/game, {a} scores {as_avg}/game"
        elif exp >= 2.2:
            out["goals"] = f"Goals expected — {h} scores {hs_avg}, concedes {hc_avg} per game · {a} scores {as_avg}, concedes {ac_avg}"
        else:
            out["goals"] = f"Tight match likely — {h} concedes {hc_avg}/game, {a} concedes {ac_avg}/game. Under 2.5 has claims"

    # Injuries
    missing = []
    if h_inj: missing.append(f"{h}: {', '.join(i['name'] for i in h_inj[:2])}")
    if a_inj: missing.append(f"{a}: {', '.join(i['name'] for i in a_inj[:2])}")
    if missing:
        out["injuries"] = " · ".join(missing) + " sidelined"

    return out
