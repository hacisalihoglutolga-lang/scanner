import sqlite3
import json
from datetime import datetime

DB_PATH = "signals.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    try:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                action TEXT NOT NULL,
                score REAL,
                price REAL,
                sl REAL,
                tp REAL,
                data TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_signals_ticker ON signals(ticker)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_signals_created ON signals(created_at DESC)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_signals_action ON signals(action)")
        # Eski kayıtları temizle (90 günden eski)
        c.execute("DELETE FROM signals WHERE created_at < datetime('now', '-90 days')")
        conn.commit()
    finally:
        conn.close()


def save_signal(ticker, action, score, price, sl, tp, data):
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("""
            INSERT INTO signals (ticker, action, score, price, sl, tp, data, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (ticker, action, score, price, sl, tp, json.dumps(data), datetime.now().isoformat()))
        conn.commit()
    finally:
        conn.close()


def get_recent_signals(limit=50):
    """Her hisse için en son sinyali döndürür, skor ve tarihe göre sıralar."""
    conn = sqlite3.connect(DB_PATH)
    try:
        c = conn.cursor()
        # Her hisse için en son kaydı al (ROW_NUMBER ile)
        c.execute("""
            WITH latest AS (
                SELECT ticker, action, score, price, sl, tp, data, created_at,
                       ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY created_at DESC) AS rn
                FROM signals
            )
            SELECT ticker, action, score, price, sl, tp, data, created_at
            FROM latest
            WHERE rn = 1
            ORDER BY
                CASE action
                    WHEN 'GÜÇLÜ AL' THEN 1
                    WHEN 'AL'       THEN 2
                    WHEN 'İZLE'     THEN 3
                    WHEN 'ZAYIF'    THEN 4
                    WHEN 'SAT'      THEN 5
                    ELSE 6
                END,
                score DESC
            LIMIT ?
        """, (limit,))
        rows = c.fetchall()
    finally:
        conn.close()
    result = []
    for r in rows:
        try:
            d = json.loads(r[6] or '{}')
            tp2        = d.get("tp2") or (d.get("tf_1d") or {}).get("tp2")
            action_4h  = d.get("action_4h")
            action_1d  = d.get("action_1d")
            action_1w  = d.get("action_1w")
            action_1mo = d.get("action_1mo")
            score_4h   = (d.get("tf_4h")  or {}).get("score")
            score_1d   = (d.get("tf_1d")  or {}).get("score")
            score_1w   = (d.get("tf_1w")  or {}).get("score")
            score_1mo  = (d.get("tf_1mo") or {}).get("score")
        except Exception:
            tp2 = action_4h = action_1d = action_1w = action_1mo = None
            score_4h = score_1d = score_1w = score_1mo = None
        result.append({
            "ticker": r[0], "action": r[1], "score": r[2],
            "price": r[3], "sl": r[4], "tp": r[5], "tp2": tp2,
            "created_at": r[7],
            "action_4h": action_4h, "score_4h": score_4h,
            "action_1d": action_1d, "score_1d": score_1d,
            "action_1w": action_1w, "score_1w": score_1w,
            "action_1mo": action_1mo, "score_1mo": score_1mo,
        })
    return result
