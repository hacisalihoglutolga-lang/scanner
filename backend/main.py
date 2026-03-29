from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Optional
import time
import math
import json
import os
from analyzer import analyze_stock
from stocks import CATEGORIES
from database import init_db, save_signal, get_recent_signals
from portfolio import full_portfolio_analysis, single_stock_deep_analysis, generate_equity_research
from screener import run_screen
from patterns import scan_patterns, analyze_patterns
from backtest import (backtest_tickers, compute_stats, evolve_params,
                      save_results, load_results, load_params, save_params,
                      correlation_analysis)
from auth import (init_users_db, login, verify_token, require_admin,
                  list_users, create_user, delete_user, change_password)

def _sanitize(obj):
    """Recursively replace nan/inf with None so FastAPI can serialize it."""
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    return obj


app = FastAPI(title="BIST Scanner API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Auth Middleware ────────────────────────────────────────────────────────────
from fastapi import Request
from fastapi.responses import JSONResponse
import jwt as _jwt

_PUBLIC = {"/api/login", "/health"}

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    # Public rotalar ve static dosyalar
    if not path.startswith("/api/") or path in _PUBLIC:
        return await call_next(request)
    # Token kontrol
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return JSONResponse(status_code=401, content={"detail": "Giriş yapmanız gerekiyor"})
    token = auth[7:]
    try:
        from auth import JWT_SECRET
        _jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except _jwt.ExpiredSignatureError:
        return JSONResponse(status_code=401, content={"detail": "Token süresi doldu"})
    except _jwt.InvalidTokenError:
        return JSONResponse(status_code=401, content={"detail": "Geçersiz token"})
    return await call_next(request)

# In-memory cache
_cache: dict = {}
_cache_time: dict = {}
CACHE_TTL = 1800  # 30 minutes

executor = ThreadPoolExecutor(max_workers=4)
_yf_semaphore: asyncio.Semaphore | None = None

# Permanently delisted tickers — never queried again
_DELISTED_FILE = os.path.join(os.path.dirname(__file__), "delisted.json")

def _load_delisted() -> set:
    try:
        with open(_DELISTED_FILE) as f:
            return set(json.load(f))
    except Exception:
        return set()

def _save_delisted(s: set):
    try:
        with open(_DELISTED_FILE, "w") as f:
            json.dump(sorted(s), f)
    except Exception:
        pass

_delisted: set = _load_delisted()

# Tracks tickers currently being fetched — prevents duplicate concurrent fetches
_in_progress: set = set()

# Temporarily skip cache for non-delisted failures (10 min)
_skip_cache: dict = {}  # ticker -> expiry timestamp
SKIP_TTL = 600


def _safe_analyze(ticker: str) -> dict | None:
    return analyze_stock(ticker)

@app.on_event("startup")
async def startup():
    global _yf_semaphore
    _yf_semaphore = asyncio.Semaphore(4)
    init_db()
    init_users_db()


# ── Auth endpoints ─────────────────────────────────────────────────────────────

@app.post("/api/login")
async def api_login(body: dict):
    username = body.get("username", "").strip()
    password = body.get("password", "")
    if not username or not password:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Kullanıcı adı ve şifre gerekli")
    token = login(username, password)
    return {"token": token, "username": username}


@app.get("/api/users", dependencies=[Depends(require_admin)])
async def api_list_users():
    return {"users": list_users()}


@app.post("/api/users", dependencies=[Depends(require_admin)])
async def api_create_user(body: dict):
    username = body.get("username", "").strip()
    password = body.get("password", "")
    is_admin = bool(body.get("is_admin", False))
    if not username or not password:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Kullanıcı adı ve şifre gerekli")
    create_user(username, password, is_admin)
    return {"message": f"{username} oluşturuldu"}


@app.delete("/api/users/{user_id}", dependencies=[Depends(require_admin)])
async def api_delete_user(user_id: int):
    delete_user(user_id)
    return {"message": "Kullanıcı silindi"}


@app.post("/api/users/{user_id}/password")
async def api_change_password(user_id: int, body: dict, payload: dict = Depends(verify_token)):
    if not payload.get("admin") and payload.get("uid") != user_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Yetki yok")
    new_password = body.get("password", "")
    if not new_password:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Yeni şifre gerekli")
    change_password(user_id, new_password)
    return {"message": "Şifre güncellendi"}


def _cached(ticker: str) -> dict | None:
    if ticker in _cache and (time.time() - _cache_time.get(ticker, 0)) < CACHE_TTL:
        return _cache[ticker]
    return None


async def _fetch_and_cache(ticker: str) -> dict | None:
    if ticker in _delisted:
        return None

    # Skip if temporarily failed
    if _skip_cache.get(ticker, 0) > time.time():
        return None

    cached = _cached(ticker)
    if cached:
        return cached

    # Skip if already being fetched
    if ticker in _in_progress:
        return None
    _in_progress.add(ticker)

    try:
        loop = asyncio.get_event_loop()
        async with _yf_semaphore:
            result = await loop.run_in_executor(executor, _safe_analyze, ticker)

        if result and not result.get("error"):
            result = _sanitize(result)
            _cache[ticker] = result
            _cache_time[ticker] = time.time()
            action = result.get("ai_action", "")
            notable = {"GÜÇLÜ AL", "AL", "İZLE"}
            has_signal = (
                action in notable or
                result.get("action_1d")  in notable or
                result.get("action_1w")  in notable or
                result.get("action_1mo") in notable
            )
            if has_signal:
                try:
                    save_signal(
                        ticker=ticker,
                        action=action,
                        score=result.get("ai_score", 0),
                        price=result.get("price", 0),
                        sl=result.get("sl", 0),
                        tp=result.get("tp1", 0),
                        data=result
                    )
                except Exception:
                    pass
        elif result and result.get("error"):
            err = result.get("error", "").lower()
            # Only permanently blacklist tickers that are truly gone from exchange
            if any(kw in err for kw in ("delisted", "no data found", "not found", "symbol may be delisted")):
                _delisted.add(ticker)
                _save_delisted(_delisted)
            else:
                # Temporarily skip (rate limit, insufficient data, etc.) — retry in 10 min
                _skip_cache[ticker] = time.time() + SKIP_TTL

        return result
    finally:
        _in_progress.discard(ticker)


@app.get("/api/stock/{ticker}")
async def get_stock(ticker: str):
    result = await _fetch_and_cache(ticker.upper())
    if not result:
        return {"error": "Veri alınamadı"}
    return result


@app.get("/api/scan")
async def scan_stocks(
    category: str = "BIST30",
    action_filter: Optional[str] = None,
    min_score: float = 0,
    limit: int = 1000
):
    stocks = CATEGORIES.get(category.upper(), CATEGORIES["BIST30"])[:limit]

    tasks = [_fetch_and_cache(t) for t in stocks]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    out = []
    for r in results:
        if isinstance(r, Exception) or r is None:
            continue
        if r.get("error"):
            continue
        if action_filter and r.get("ai_action") != action_filter:
            continue
        if r.get("ai_score", 0) < min_score:
            continue
        out.append(r)

    _ACT_ORD   = {"GÜÇLÜ AL": 0, "AL": 1, "İZLE": 2, "ZAYIF": 3, "SAT": 4}
    _SETUP_ORD = {"KIRILIM": 0, "DÖNÜŞ": 1, "STANDART": 2}
    out.sort(key=lambda x: (
        _ACT_ORD.get(x.get("ai_action", ""), 5),
        _SETUP_ORD.get(x.get("setup_type", "STANDART"), 2),
        -(x.get("ai_score") or 0),
    ))
    return {"stocks": out, "total": len(out), "category": category}


@app.get("/api/scan/stream")
async def scan_stream(category: str = "BIST30", limit: int = 1000, force: bool = False):
    """Return cached results immediately, trigger background refresh."""
    stocks = CATEGORIES.get(category.upper(), CATEGORIES["BIST30"])[:limit]

    # force=True: bust cache for this category so fresh analysis runs
    if force:
        for t in stocks:
            _cache.pop(t, None)
            _cache_time.pop(t, None)
            _skip_cache.pop(t, None)

    out = []
    stale = []
    now = time.time()
    pending = []   # not yet started
    for t in stocks:
        if t in _delisted:
            continue
        if _skip_cache.get(t, 0) > now:
            continue
        cached = _cached(t)
        if cached:
            out.append(cached)
        elif t in _in_progress:
            pending.append(t)   # already running — still pending from frontend's view
        else:
            pending.append(t)   # not started yet

    # Start background fetch only for tickers not already in progress
    new_stale = [t for t in pending if t not in _in_progress]
    if new_stale:
        asyncio.create_task(_refresh_batch(new_stale))

    _ACT_ORD   = {"GÜÇLÜ AL": 0, "AL": 1, "İZLE": 2, "ZAYIF": 3, "SAT": 4}
    _SETUP_ORD = {"KIRILIM": 0, "DÖNÜŞ": 1, "STANDART": 2}
    out.sort(key=lambda x: (
        _ACT_ORD.get(x.get("ai_action", ""), 5),
        _SETUP_ORD.get(x.get("setup_type", "STANDART"), 2),
        -(x.get("ai_score") or 0),
    ))
    return {"stocks": out, "pending": pending, "total": len(out)}


async def _refresh_batch(tickers: list[str]):
    tasks = [_fetch_and_cache(t) for t in tickers]
    await asyncio.gather(*tasks, return_exceptions=True)


@app.get("/api/stocks")
async def list_stocks():
    return {"categories": {k: v for k, v in CATEGORIES.items()}}


@app.get("/api/signals/recent")
async def recent_signals(limit: int = 50):
    return {"signals": get_recent_signals(limit)}


@app.get("/api/stock/{ticker}/ohlcv")
async def get_ohlcv(ticker: str, days: int = 180, interval: str = "1d"):
    """Mum grafik için OHLCV verisi döndürür. interval: 1h, 1d, 1wk"""
    import yfinance as yf
    loop = asyncio.get_event_loop()
    def _fetch():
        try:
            import yfinance as yf
            from analyzer import _yf_session
            t = yf.Ticker(f"{ticker.upper()}.IS", session=_yf_session)
            yf_interval = {"1h": "1h", "4h": "1h", "1d": "1d", "1wk": "1wk"}.get(interval, "1d")
            actual_days = min(days, 59) if interval in ("1h", "4h") else days
            df = t.history(period=f"{actual_days}d", interval=yf_interval)
            if df is None or df.empty:
                return None
            if interval == "4h":
                df = df.resample("4h").agg(
                    {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
                ).dropna()
            out = []
            for ts, row in df.iterrows():
                out.append({
                    "time":   int(ts.timestamp()),
                    "open":   round(float(row["Open"]),   2),
                    "high":   round(float(row["High"]),   2),
                    "low":    round(float(row["Low"]),    2),
                    "close":  round(float(row["Close"]),  2),
                    "volume": int(row["Volume"]),
                })
            return out
        except Exception as e:
            err = str(e).lower()
            if "rate limit" in err or "too many" in err or "429" in err:
                return {"__error__": "rate_limit"}
            return {"__error__": str(e)}

    data = await loop.run_in_executor(executor, _fetch)
    if not data:
        return {"error": "Veri alınamadı", "data": []}
    if isinstance(data, dict) and "__error__" in data:
        msg = "Yahoo Finance rate limit — birkaç dakika bekleyin" if data["__error__"] == "rate_limit" else "Veri alınamadı"
        return {"error": msg, "data": []}
    return {"ticker": ticker.upper(), "data": data}


@app.get("/api/stock/{ticker}/equity-research")
async def equity_research_endpoint(ticker: str):
    """Tek bir hisse için Claude AI destekli equity research raporu."""
    result = await generate_equity_research(ticker.upper())
    return result


@app.get("/api/stock/{ticker}/deep-analysis")
async def stock_deep_analysis(ticker: str):
    """Tek bir hisse için kurumsal AI analizi (GS, MS, Bridgewater, Two Sigma)."""
    result = await single_stock_deep_analysis(ticker.upper())
    return result


@app.get("/api/pattern-scan")
async def pattern_scan_endpoint(category: str = "BIST30", direction: str = "all"):
    """Formasyon tarayıcısı: tüm hisseleri klasik formasyonlar + Elliott Wave açısından tarar."""
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(
        executor,
        lambda: scan_patterns(category, direction, _cache)
    )
    return {"stocks": results, "total": len(results)}


@app.get("/api/stock/{ticker}/patterns")
async def stock_patterns_endpoint(ticker: str):
    """Tek bir hisse için formasyon analizi."""
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        executor,
        lambda: analyze_patterns(ticker.upper(), _cache)
    )
    return result or {"ticker": ticker, "patterns": [], "error": "Veri alınamadı"}


@app.post("/api/screen")
async def screen_stocks_endpoint(body: dict):
    """Temel tarayıcı: filtrele ve sonuçları döndür."""
    category = body.get("category", "BIST100")
    filters  = body.get("filters", [])
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(
        executor,
        lambda: run_screen(category, filters, _cache)
    )
    return {"stocks": results, "total": len(results)}


@app.delete("/api/cache")
async def clear_cache():
    _cache.clear()
    _cache_time.clear()
    return {"message": "Cache temizlendi"}


@app.post("/api/portfolio/analyze")
async def analyze_portfolio(payload: dict):
    """
    payload: { "holdings": [{"ticker": "GARAN", "shares": 1000, "avg_cost": 95.0}, ...] }
    """
    holdings = payload.get("holdings", [])
    if not holdings:
        return {"error": "Portföy boş"}
    # full_portfolio_analysis handles its own async AI calls
    result = await full_portfolio_analysis(holdings)
    return result


@app.get("/health")
async def health():
    return {"status": "ok", "cached": len(_cache)}


# ─── Backtest endpoints ───────────────────────────────────────────────────────

_bt_progress: dict = {"done": 0, "total": 0, "current": "", "running": False}


@app.post("/api/backtest/run")
async def run_backtest(body: dict):
    """
    Backtest başlat (arka planda).
    body: { "category": "BIST30", "lookback_days": 365, "step_days": 5 }
    """
    global _bt_progress
    if _bt_progress["running"]:
        return {"error": "Backtest zaten çalışıyor", "progress": _bt_progress}

    category          = body.get("category", "BIST30")
    lookback_days     = int(body.get("lookback_days", 365))
    step_days         = int(body.get("step_days", 5))
    fresh_only        = bool(body.get("fresh_signals_only", True))
    market_filter     = bool(body.get("market_filter", True))

    tickers = CATEGORIES.get(category, CATEGORIES.get("BIST30", []))

    def _run():
        global _bt_progress
        _bt_progress = {"done": 0, "total": len(tickers), "current": "", "running": True}

        def _cb(done, total, ticker):
            _bt_progress["done"]    = done
            _bt_progress["total"]   = total
            _bt_progress["current"] = ticker

        try:
            results = backtest_tickers(tickers, lookback_days, step_days,
                                       max_workers=3, progress_cb=_cb,
                                       fresh_signals_only=fresh_only,
                                       market_filter=market_filter)
            save_results(results)
        finally:
            _bt_progress["running"] = False
            _bt_progress["current"] = ""

    import threading
    threading.Thread(target=_run, daemon=True).start()
    return {"message": f"{len(tickers)} hisse için backtest başlatıldı", "progress": _bt_progress}


@app.get("/api/backtest/progress")
async def backtest_progress():
    return _bt_progress


@app.get("/api/backtest/stats")
async def backtest_stats():
    """Kaydedilmiş backtest sonuçlarından istatistik döndür."""
    results = load_results()
    if not results:
        return {"error": "Henüz backtest çalıştırılmadı"}
    stats = compute_stats(results)
    return _sanitize({"stats": stats, "total_signals": len(results)})


@app.get("/api/backtest/results")
async def backtest_results(action: str = "GÜÇLÜ AL", limit: int = 100):
    """Ham sinyal sonuçları (filtreli)."""
    results = load_results()
    filtered = [r for r in results if r.get("action") == action] if action != "TÜMÜ" else results
    return _sanitize({"results": filtered[:limit], "total": len(filtered)})


@app.post("/api/backtest/evolve")
async def backtest_evolve(body: dict):
    """Mevcut backtest sonuçlarına göre parametreleri optimize et ve kaydet."""
    target = body.get("target_action", "GÜÇLÜ AL")
    results = load_results()
    if not results:
        return {"error": "Önce backtest çalıştır"}

    new_params = evolve_params(results, target_action=target)
    save_params(new_params)
    return {"message": "Parametreler güncellendi", "params": new_params}


@app.get("/api/backtest/correlation")
async def backtest_correlation():
    """Skor-getiri korelasyon analizi."""
    results = load_results()
    if not results:
        return {"error": "Önce backtest çalıştır"}
    return _sanitize(correlation_analysis(results))


@app.get("/api/backtest/params")
async def get_backtest_params():
    return load_params()


@app.post("/api/backtest/params")
async def set_backtest_params(body: dict):
    """Manuel parametre güncelleme."""
    save_params(body)
    return {"message": "Parametreler kaydedildi", "params": body}


# --- Static frontend servisi (production build) ---
_DIST = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(_DIST, "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        index = os.path.join(_DIST, "index.html")
        return FileResponse(index)
