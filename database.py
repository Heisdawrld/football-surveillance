"""
database.py -- ProPredictor persistence layer v2
Full tracker support: seeded demo data, performance stats, reliability scores.
"""
import sqlite3, os, json
from datetime import datetime, timezone, timedelta

DB_PATH = os.environ.get("DB_PATH", "propredictor.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_conn() as conn:
        # Create tables if they don't exist (safe on fresh DB)
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS predictions (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id            INTEGER NOT NULL,
            league_id           INTEGER,
            league_name         TEXT,
            home_team           TEXT,
            away_team           TEXT,
            match_date          TEXT,
            market              TEXT,
            probability         REAL,
            fair_odds           REAL,
            bookie_odds         REAL,
            edge                REAL,
            confidence          REAL,
            xg_home             REAL,
            xg_away             REAL,
            likely_score        TEXT,
            logged_at           TEXT,
            actual_home_score   INTEGER DEFAULT NULL,
            actual_away_score   INTEGER DEFAULT NULL,
            result              TEXT DEFAULT NULL,
            settled_at          TEXT DEFAULT NULL,
            UNIQUE(match_id, market)
        );
        CREATE TABLE IF NOT EXISTS h2h_cache (
            cache_key   TEXT PRIMARY KEY,
            data        TEXT,
            cached_at   TEXT
        );
        CREATE TABLE IF NOT EXISTS injury_cache (
            cache_key   TEXT PRIMARY KEY,
            data        TEXT,
            cached_at   TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_pred_league ON predictions(league_id);
        CREATE INDEX IF NOT EXISTS idx_pred_market ON predictions(market);
        CREATE INDEX IF NOT EXISTS idx_pred_result ON predictions(result);
        CREATE INDEX IF NOT EXISTS idx_pred_date   ON predictions(match_date);

        CREATE TABLE IF NOT EXISTS team_memory (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            team_name      TEXT NOT NULL,
            opponent       TEXT NOT NULL,
            league         TEXT,
            venue          TEXT NOT NULL,
            result         TEXT NOT NULL,
            goals_scored   INTEGER DEFAULT 0,
            goals_conceded INTEGER DEFAULT 0,
            gg_hit         INTEGER DEFAULT 0,
            over25_hit     INTEGER DEFAULT 0,
            over15_hit     INTEGER DEFAULT 0,
            match_date     TEXT,
            logged_at      TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_tm_team    ON team_memory(team_name);
        CREATE INDEX IF NOT EXISTS idx_tm_venue   ON team_memory(team_name, venue);
        CREATE INDEX IF NOT EXISTS idx_tm_h2h     ON team_memory(team_name, opponent);

        CREATE TABLE IF NOT EXISTS team_profile (
            team_name         TEXT PRIMARY KEY,
            league            TEXT,
            home_played       INTEGER DEFAULT 0,
            home_wins         INTEGER DEFAULT 0,
            home_draws        INTEGER DEFAULT 0,
            home_losses       INTEGER DEFAULT 0,
            home_goals_for    REAL DEFAULT 0,
            home_goals_ag     REAL DEFAULT 0,
            home_gg           INTEGER DEFAULT 0,
            home_over25       INTEGER DEFAULT 0,
            home_clean_sheets INTEGER DEFAULT 0,
            away_played       INTEGER DEFAULT 0,
            away_wins         INTEGER DEFAULT 0,
            away_draws        INTEGER DEFAULT 0,
            away_losses       INTEGER DEFAULT 0,
            away_goals_for    REAL DEFAULT 0,
            away_goals_ag     REAL DEFAULT 0,
            away_gg           INTEGER DEFAULT 0,
            away_over25       INTEGER DEFAULT 0,
            away_clean_sheets INTEGER DEFAULT 0,
            last_updated      TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_tp_team ON team_profile(team_name);

        CREATE TABLE IF NOT EXISTS market_calibration (
            market             TEXT PRIMARY KEY,
            total              INTEGER DEFAULT 0,
            wins               INTEGER DEFAULT 0,
            avg_prob           REAL DEFAULT 50.0,
            hit_rate           REAL DEFAULT 50.0,
            calibration_factor REAL DEFAULT 1.0,
            last_updated       TEXT
        );
        """)
        # -- Safe migration: add new columns if they don't exist --
        # This handles both fresh DBs and existing deployed DBs on Render
        existing_cols = {r[1] for r in conn.execute("PRAGMA table_info(predictions)").fetchall()}
        migrations = [
            ("tag",               "TEXT"),
            ("reliability_score", "REAL DEFAULT NULL"),
        ]
        for col, col_type in migrations:
            if col not in existing_cols:
                try:
                    conn.execute(f"ALTER TABLE predictions ADD COLUMN {col} {col_type}")
                    print(f"[DB] migrated: added column '{col}'")
                except Exception as e:
                    print(f"[DB] migration warning for '{col}': {e}")




def log_prediction(match_id, league_id, league_name, home_team, away_team,
                   match_date, market, probability, fair_odds, bookie_odds,
                   edge, confidence, xg_home, xg_away, likely_score,
                   tag=None, reliability_score=None):
    try:
        with get_conn() as conn:
            conn.execute("""
                INSERT OR IGNORE INTO predictions
                (match_id, league_id, league_name, home_team, away_team,
                 match_date, market, probability, fair_odds, bookie_odds,
                 edge, confidence, xg_home, xg_away, likely_score,
                 tag, reliability_score, logged_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (match_id, league_id, league_name, home_team, away_team,
                  match_date, market, probability, fair_odds, bookie_odds,
                  edge, confidence, xg_home, xg_away, likely_score,
                  tag, reliability_score,
                  datetime.now(timezone.utc).isoformat()))
    except Exception as e:
        print(f"[DB] log_prediction: {e}")

def settle_prediction(match_id, market, home_score, away_score):
    result = _evaluate_result(market, home_score, away_score)
    try:
        with get_conn() as conn:
            conn.execute("""
                UPDATE predictions
                SET actual_home_score=?, actual_away_score=?,
                    result=?, settled_at=?
                WHERE match_id=? AND market=? AND result IS NULL
            """, (home_score, away_score, result,
                  datetime.now(timezone.utc).isoformat(),
                  match_id, market))
    except Exception as e:
        print(f"[DB] settle: {e}")

def _evaluate_result(market, h, a):
    try:
        total = h + a
        m = market.upper()
        if "HOME WIN" in m:  return "WIN" if h > a else "LOSS"
        if "AWAY WIN" in m:  return "WIN" if a > h else "LOSS"
        if m == "DRAW":      return "WIN" if h == a else "LOSS"
        if "OVER 1.5" in m:  return "WIN" if total > 1 else "LOSS"
        if "OVER 2.5" in m:  return "WIN" if total > 2 else "LOSS"
        if "OVER 3.5" in m:  return "WIN" if total > 3 else "LOSS"
        if "UNDER 2.5" in m: return "WIN" if total <= 2 else "LOSS"
        if "UNDER 1.5" in m: return "WIN" if total <= 1 else "LOSS"
        if m in ("GG","BTTS","BTTS YES"):
            return "WIN" if h > 0 and a > 0 else "LOSS"
        if m in ("NG","BTTS NO"):
            return "WIN" if (h == 0 or a == 0) else "LOSS"
        return "VOID"
    except:
        return "VOID"

def get_tracker_stats():
    with get_conn() as conn:
        total = conn.execute(
            "SELECT COUNT(*) as n FROM predictions WHERE result IN ('WIN','LOSS')"
        ).fetchone()["n"]
        wins  = conn.execute(
            "SELECT COUNT(*) as n FROM predictions WHERE result='WIN'"
        ).fetchone()["n"]
        # Rolling 7-day
        week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        week_total = conn.execute(
            "SELECT COUNT(*) as n FROM predictions WHERE result IN ('WIN','LOSS') AND settled_at >= ?",
            (week_ago,)
        ).fetchone()["n"]
        week_wins = conn.execute(
            "SELECT COUNT(*) as n FROM predictions WHERE result='WIN' AND settled_at >= ?",
            (week_ago,)
        ).fetchone()["n"]
        # By market
        by_market = conn.execute("""
            SELECT market,
                   COUNT(*) as total,
                   SUM(CASE WHEN result='WIN' THEN 1 ELSE 0 END) as wins,
                   AVG(probability) as avg_prob,
                   AVG(edge) as avg_edge
            FROM predictions WHERE result IN ('WIN','LOSS')
            GROUP BY market ORDER BY total DESC
        """).fetchall()
        # By league
        by_league = conn.execute("""
            SELECT league_name,
                   COUNT(*) as total,
                   SUM(CASE WHEN result='WIN' THEN 1 ELSE 0 END) as wins
            FROM predictions WHERE result IN ('WIN','LOSS')
            GROUP BY league_name ORDER BY total DESC LIMIT 8
        """).fetchall()
        # Recent 15
        recent = conn.execute("""
            SELECT home_team, away_team, market, probability,
                   fair_odds, edge, result, match_date, league_name,
                   actual_home_score, actual_away_score, tag
            FROM predictions WHERE result IN ('WIN','LOSS')
            ORDER BY settled_at DESC LIMIT 15
        """).fetchall()
        # Pending
        pending_rows = conn.execute("""
            SELECT home_team, away_team, market, probability,
                   fair_odds, match_date, league_name, tag
            FROM predictions WHERE result IS NULL
            ORDER BY logged_at DESC LIMIT 10
        """).fetchall()
        pending_count = conn.execute(
            "SELECT COUNT(*) as n FROM predictions WHERE result IS NULL"
        ).fetchone()["n"]
        # Streak
        last10 = conn.execute("""
            SELECT result FROM predictions WHERE result IN ('WIN','LOSS')
            ORDER BY settled_at DESC LIMIT 10
        """).fetchall()
        streak = _calc_streak([r["result"] for r in last10])
        # ROI (assuming 1 unit per bet at fair odds)
        roi_data = conn.execute("""
            SELECT result, fair_odds FROM predictions
            WHERE result IN ('WIN','LOSS') AND fair_odds IS NOT NULL
        """).fetchall()
        roi = _calc_roi(roi_data)

        hit_rate      = round(wins / total * 100, 1) if total > 0 else 0
        week_hit_rate = round(week_wins / week_total * 100, 1) if week_total > 0 else 0

        return {
            "total": total, "wins": wins, "losses": total-wins,
            "hit_rate": hit_rate, "pending": pending_count,
            "week_total": week_total, "week_wins": week_wins,
            "week_hit_rate": week_hit_rate,
            "by_market": [dict(r) for r in by_market],
            "by_league": [dict(r) for r in by_league],
            "recent":    [dict(r) for r in recent],
            "pending_rows": [dict(r) for r in pending_rows],
            "streak": streak,
            "roi":    roi,
        }

def _calc_streak(results):
    if not results: return {"type":"--","count":0}
    cur = results[0]; count = 1
    for r in results[1:]:
        if r == cur: count += 1
        else: break
    return {"type": cur, "count": count}

def _calc_roi(rows):
    if not rows: return 0.0
    profit = 0.0
    for r in rows:
        if r["result"] == "WIN":
            profit += (r["fair_odds"] - 1)
        else:
            profit -= 1.0
    roi = (profit / len(rows)) * 100
    return round(roi, 1)

def get_recent_pending(limit=50):
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT match_id, market, home_team, away_team, match_date
            FROM predictions WHERE result IS NULL
            ORDER BY logged_at ASC LIMIT ?
        """, (limit,)).fetchall()
    return [dict(r) for r in rows]


def update_team_memory(home_team, away_team, league,
                       home_score, away_score, match_date=None):
    """
    After a match settles, record actual performance for both teams.

    Arsenal 3-1 Wolves:
      Arsenal  -> home, WIN,  scored=3, conceded=1, gg=1, over25=1
      Wolves   -> away, LOSS, scored=1, conceded=3, gg=1, over25=1

    This builds real per-team intelligence from our own settled data.
    Completely independent of any external API.
    """
    try:
        h = int(home_score); a = int(away_score)
        total   = h + a
        gg      = 1 if h > 0 and a > 0 else 0
        over25  = 1 if total > 2 else 0
        over15  = 1 if total > 1 else 0
        h_res   = "W" if h > a else "D" if h == a else "L"
        a_res   = "W" if a > h else "D" if h == a else "L"
        now     = datetime.now(timezone.utc).isoformat()
        mdate   = match_date or now[:10]

        with get_conn() as conn:
            # Store individual match records
            conn.execute("""
                INSERT INTO team_memory
                (team_name, opponent, league, venue, result,
                 goals_scored, goals_conceded, gg_hit, over25_hit, over15_hit,
                 match_date, logged_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, (home_team, away_team, league, "home", h_res,
                  h, a, gg, over25, over15, mdate, now))

            conn.execute("""
                INSERT INTO team_memory
                (team_name, opponent, league, venue, result,
                 goals_scored, goals_conceded, gg_hit, over25_hit, over15_hit,
                 match_date, logged_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, (away_team, home_team, league, "away", a_res,
                  a, h, gg, over25, over15, mdate, now))

            # Update team profiles
            for team, venue, gf, ga, res in [
                (home_team, "home", h, a, h_res),
                (away_team, "away", a, h, a_res),
            ]:
                existing = conn.execute(
                    "SELECT * FROM team_profile WHERE team_name=?",
                    (team,)).fetchone()

                cs = 1 if ga == 0 else 0
                w  = 1 if res == "W" else 0
                d  = 1 if res == "D" else 0
                l  = 1 if res == "L" else 0

                if existing:
                    if venue == "home":
                        hp  = existing["home_played"] + 1
                        hgf = existing["home_goals_for"] + gf
                        hga = existing["home_goals_ag"] + ga
                        conn.execute("""
                            UPDATE team_profile SET
                            home_played=?, home_wins=home_wins+?,
                            home_draws=home_draws+?, home_losses=home_losses+?,
                            home_goals_for=?, home_goals_ag=?,
                            home_gg=home_gg+?, home_over25=home_over25+?,
                            home_clean_sheets=home_clean_sheets+?,
                            last_updated=? WHERE team_name=?
                        """, (hp, w, d, l, hgf, hga, gg, over25, cs, now, team))
                    else:
                        ap  = existing["away_played"] + 1
                        agf = existing["away_goals_for"] + gf
                        aga = existing["away_goals_ag"] + ga
                        conn.execute("""
                            UPDATE team_profile SET
                            away_played=?, away_wins=away_wins+?,
                            away_draws=away_draws+?, away_losses=away_losses+?,
                            away_goals_for=?, away_goals_ag=?,
                            away_gg=away_gg+?, away_over25=away_over25+?,
                            away_clean_sheets=away_clean_sheets+?,
                            last_updated=? WHERE team_name=?
                        """, (ap, w, d, l, agf, aga, gg, over25, cs, now, team))
                else:
                    if venue == "home":
                        conn.execute("""
                            INSERT INTO team_profile
                            (team_name, league, home_played,
                             home_wins, home_draws, home_losses,
                             home_goals_for, home_goals_ag,
                             home_gg, home_over25, home_clean_sheets,
                             away_played, last_updated)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,0,?)
                        """, (team, league, 1, w, d, l, gf, ga,
                              gg, over25, cs, now))
                    else:
                        conn.execute("""
                            INSERT INTO team_profile
                            (team_name, league, away_played,
                             away_wins, away_draws, away_losses,
                             away_goals_for, away_goals_ag,
                             away_gg, away_over25, away_clean_sheets,
                             home_played, last_updated)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,0,?)
                        """, (team, league, 1, w, d, l, gf, ga,
                              gg, over25, cs, now))

    except Exception as e:
        print(f"[DB] update_team_memory: {e}")

def get_market_calibration():
    """
    Returns calibration data for markets with 20+ samples.
    Used by match_predictor to auto-adjust conviction scores.
    """
    try:
        with get_conn() as conn:
            rows = conn.execute("""
                SELECT market, total, wins, avg_prob, hit_rate, calibration_factor
                FROM market_calibration WHERE total >= 20
                ORDER BY total DESC
            """).fetchall()
        return {r["market"]: dict(r) for r in rows}
    except:
        return {}

def get_team_profile(team_name, venue="home", min_matches=5):
    """
    Get a team's real performance profile from our own settled data.

    Returns per-venue stats:
      win_rate, avg_goals_scored, avg_goals_conceded,
      gg_rate, over25_rate, clean_sheet_rate

    Used by match_predictor to adjust xG and conviction
    based on what this team ACTUALLY does, not just what
    the API says.

    Returns None if less than min_matches recorded.
    """
    try:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM team_profile WHERE team_name=?",
                (team_name,)).fetchone()
        if not row:
            return None

        if venue == "home":
            played = row["home_played"] or 0
            if played < min_matches:
                return None
            wins   = row["home_wins"]   or 0
            draws  = row["home_draws"]  or 0
            losses = row["home_losses"] or 0
            gf     = row["home_goals_for"] or 0
            ga     = row["home_goals_ag"]  or 0
            gg     = row["home_gg"]        or 0
            o25    = row["home_over25"]    or 0
            cs     = row["home_clean_sheets"] or 0
        else:
            played = row["away_played"] or 0
            if played < min_matches:
                return None
            wins   = row["away_wins"]   or 0
            draws  = row["away_draws"]  or 0
            losses = row["away_losses"] or 0
            gf     = row["away_goals_for"] or 0
            ga     = row["away_goals_ag"]  or 0
            gg     = row["away_gg"]        or 0
            o25    = row["away_over25"]    or 0
            cs     = row["away_clean_sheets"] or 0

        return {
            "team":            team_name,
            "venue":           venue,
            "played":          played,
            "wins":            wins,
            "draws":           draws,
            "losses":          losses,
            "win_rate":        round(wins  / played * 100, 1),
            "draw_rate":       round(draws / played * 100, 1),
            "loss_rate":       round(losses/ played * 100, 1),
            "avg_scored":      round(gf / played, 2),
            "avg_conceded":    round(ga / played, 2),
            "gg_rate":         round(gg  / played * 100, 1),
            "over25_rate":     round(o25 / played * 100, 1),
            "clean_sheet_rate":round(cs  / played * 100, 1),
        }
    except Exception as e:
        print(f"[DB] get_team_profile: {e}")
    return None

def get_h2h_memory(team_a, team_b, min_matches=3):
    """
    Our own head-to-head record from settled data.
    Independent of API Football -- built entirely from our tracker.
    """
    try:
        with get_conn() as conn:
            rows = conn.execute("""
                SELECT result, goals_scored, goals_conceded, gg_hit, over25_hit
                FROM team_memory
                WHERE team_name=? AND opponent=?
                ORDER BY match_date DESC LIMIT 10
            """, (team_a, team_b)).fetchall()
        if not rows or len(rows) < min_matches:
            return None
        total = len(rows)
        wins  = sum(1 for r in rows if r["result"]=="W")
        draws = sum(1 for r in rows if r["result"]=="D")
        losses= sum(1 for r in rows if r["result"]=="L")
        avg_gf = round(sum(r["goals_scored"]   for r in rows)/total, 2)
        avg_ga = round(sum(r["goals_conceded"]  for r in rows)/total, 2)
        gg_r   = round(sum(r["gg_hit"]          for r in rows)/total*100, 1)
        o25_r  = round(sum(r["over25_hit"]      for r in rows)/total*100, 1)
        return {
            "total": total, "wins": wins, "draws": draws, "losses": losses,
            "win_rate":  round(wins/total*100,1),
            "avg_scored": avg_gf, "avg_conceded": avg_ga,
            "gg_rate": gg_r, "over25_rate": o25_r,
        }
    except Exception as e:
        print(f"[DB] get_h2h_memory: {e}")
    return None

def get_team_stats_memory(team_name, market=None, min_samples=5):
    """Legacy wrapper -- use get_team_profile() for new code."""
    return get_team_profile(team_name, min_matches=min_samples)

def update_market_calibration(market, prob, win):
    """Update global market hit rate -- separate from team memory."""
    try:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT total, wins, avg_prob FROM market_calibration WHERE market=?",
                (market,)).fetchone()
            now = datetime.now(timezone.utc).isoformat()
            if row:
                new_total = row["total"] + 1
                new_wins  = row["wins"] + win
                new_avg   = (row["avg_prob"] * row["total"] + prob) / new_total
                new_hr    = round(new_wins / new_total * 100, 2)
                new_cf    = round(new_hr / max(new_avg, 1), 3)
                conn.execute("""
                    UPDATE market_calibration
                    SET total=?, wins=?, avg_prob=?, hit_rate=?,
                        calibration_factor=?, last_updated=?
                    WHERE market=?
                """, (new_total, new_wins, new_avg, new_hr, new_cf, now, market))
            else:
                hr = 100.0 if win else 0.0
                conn.execute("""
                    INSERT INTO market_calibration
                    (market, total, wins, avg_prob, hit_rate,
                     calibration_factor, last_updated)
                    VALUES (?,1,?,?,?,1.0,?)
                """, (market, win, prob, hr, now))
    except Exception as e:
        print(f"[DB] update_market_calibration: {e}")

def cache_set(table, key, json_str):
    with get_conn() as conn:
        conn.execute(f"""
            INSERT OR REPLACE INTO {table} (cache_key, data, cached_at)
            VALUES (?, ?, ?)
        """, (key, json_str, datetime.now(timezone.utc).isoformat()))

def cache_get(table, key, max_age_hours=24):
    with get_conn() as conn:
        row = conn.execute(
            f"SELECT data, cached_at FROM {table} WHERE cache_key=?", (key,)
        ).fetchone()
    if not row: return None
    cached_at = datetime.fromisoformat(row["cached_at"])
    if datetime.now(timezone.utc).replace(tzinfo=None) - cached_at.replace(tzinfo=None) > timedelta(hours=max_age_hours):
        return None
    return row["data"]
