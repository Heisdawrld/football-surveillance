"""
database.py — ProPredictor persistence layer
Logs every prediction, records actual results, tracks model accuracy.
Uses SQLite — zero cost, built into Python, works on Render/Railway/etc.
"""

import sqlite3
import os
from datetime import datetime, timezone

DB_PATH = os.environ.get("DB_PATH", "propredictor.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Create tables if they don't exist. Safe to call on every startup."""
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS predictions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id        INTEGER NOT NULL,
            league_id       INTEGER,
            league_name     TEXT,
            home_team       TEXT,
            away_team       TEXT,
            match_date      TEXT,
            market          TEXT,       -- e.g. 'HOME WIN', 'OVER 1.5'
            probability     REAL,       -- model prob %
            fair_odds       REAL,
            bookie_odds     REAL,       -- bookmaker odds at time of prediction
            edge            REAL,       -- value edge %
            confidence      REAL,
            xg_home         REAL,
            xg_away         REAL,
            likely_score    TEXT,
            logged_at       TEXT,
            -- Result fields (filled in after match)
            actual_home_score   INTEGER DEFAULT NULL,
            actual_away_score   INTEGER DEFAULT NULL,
            result              TEXT DEFAULT NULL,  -- 'WIN','LOSS','VOID'
            settled_at          TEXT DEFAULT NULL,
            UNIQUE(match_id, market)
        );

        CREATE TABLE IF NOT EXISTS h2h_cache (
            cache_key   TEXT PRIMARY KEY,
            data        TEXT,           -- JSON blob
            cached_at   TEXT
        );

        CREATE TABLE IF NOT EXISTS injury_cache (
            cache_key   TEXT PRIMARY KEY,
            data        TEXT,
            cached_at   TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_pred_league  ON predictions(league_id);
        CREATE INDEX IF NOT EXISTS idx_pred_market  ON predictions(market);
        CREATE INDEX IF NOT EXISTS idx_pred_result  ON predictions(result);
        """)

def log_prediction(match_id, league_id, league_name, home_team, away_team,
                   match_date, market, probability, fair_odds, bookie_odds,
                   edge, confidence, xg_home, xg_away, likely_score):
    """
    Store a prediction. Uses INSERT OR IGNORE so re-running won't duplicate.
    """
    try:
        with get_conn() as conn:
            conn.execute("""
                INSERT OR IGNORE INTO predictions
                (match_id, league_id, league_name, home_team, away_team,
                 match_date, market, probability, fair_odds, bookie_odds,
                 edge, confidence, xg_home, xg_away, likely_score, logged_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (match_id, league_id, league_name, home_team, away_team,
                  match_date, market, probability, fair_odds, bookie_odds,
                  edge, confidence, xg_home, xg_away, likely_score,
                  datetime.now(timezone.utc).isoformat()))
    except Exception as e:
        print(f"[DB] log_prediction error: {e}")

def settle_prediction(match_id, market, home_score, away_score):
    """
    Mark a prediction as won/lost based on actual scoreline.
    Call this after a match finishes.
    """
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
        print(f"[DB] settle_prediction error: {e}")

def _evaluate_result(market, h, a):
    """Determine WIN/LOSS from scoreline for a given market."""
    try:
        total = h + a
        if market == "HOME WIN":
            return "WIN" if h > a else "LOSS"
        elif market == "AWAY WIN":
            return "WIN" if a > h else "LOSS"
        elif market == "DRAW":
            return "WIN" if h == a else "LOSS"
        elif market == "OVER 1.5":
            return "WIN" if total > 1 else "LOSS"
        elif market == "OVER 2.5":
            return "WIN" if total > 2 else "LOSS"
        elif market == "OVER 3.5":
            return "WIN" if total > 3 else "LOSS"
        elif market == "BTTS":
            return "WIN" if h > 0 and a > 0 else "LOSS"
        else:
            return "VOID"
    except:
        return "VOID"

def get_tracker_stats():
    """
    Returns overall model performance stats.
    Used for the /tracker page.
    """
    with get_conn() as conn:
        total = conn.execute(
            "SELECT COUNT(*) as n FROM predictions WHERE result IN ('WIN','LOSS')"
        ).fetchone()["n"]

        wins = conn.execute(
            "SELECT COUNT(*) as n FROM predictions WHERE result='WIN'"
        ).fetchone()["n"]

        # By market
        by_market = conn.execute("""
            SELECT market,
                   COUNT(*) as total,
                   SUM(CASE WHEN result='WIN' THEN 1 ELSE 0 END) as wins,
                   AVG(probability) as avg_prob,
                   AVG(edge) as avg_edge
            FROM predictions
            WHERE result IN ('WIN','LOSS')
            GROUP BY market
            ORDER BY total DESC
        """).fetchall()

        # By league
        by_league = conn.execute("""
            SELECT league_name,
                   COUNT(*) as total,
                   SUM(CASE WHEN result='WIN' THEN 1 ELSE 0 END) as wins
            FROM predictions
            WHERE result IN ('WIN','LOSS')
            GROUP BY league_name
            ORDER BY total DESC
        """).fetchall()

        # Recent 20
        recent = conn.execute("""
            SELECT home_team, away_team, market, probability,
                   fair_odds, edge, result, match_date, league_name,
                   actual_home_score, actual_away_score
            FROM predictions
            WHERE result IN ('WIN','LOSS')
            ORDER BY settled_at DESC
            LIMIT 20
        """).fetchall()

        # Pending (not yet settled)
        pending = conn.execute("""
            SELECT COUNT(*) as n FROM predictions WHERE result IS NULL
        """).fetchone()["n"]

        hit_rate = round((wins / total * 100), 1) if total > 0 else 0

        return {
            "total":     total,
            "wins":      wins,
            "losses":    total - wins,
            "hit_rate":  hit_rate,
            "pending":   pending,
            "by_market": [dict(r) for r in by_market],
            "by_league": [dict(r) for r in by_league],
            "recent":    [dict(r) for r in recent],
        }

def get_recent_pending(limit=50):
    """Get unsettled predictions that might now have results."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT match_id, market, home_team, away_team, match_date
            FROM predictions
            WHERE result IS NULL
            ORDER BY logged_at ASC
            LIMIT ?
        """, (limit,)).fetchall()
    return [dict(r) for r in rows]

# ── H2H cache ────────────────────────────────────────────────────────────────
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
    if not row:
        return None
    from datetime import timedelta
    cached_at = datetime.fromisoformat(row["cached_at"])
    if datetime.now(timezone.utc) - cached_at > timedelta(hours=max_age_hours):
        return None
    return row["data"]
