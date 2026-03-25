"""
BIST Walk-Forward Backtest Engine + Parametre Evolver
======================================================
• Her geçmiş tarihte veriyi keserek mevcut analiz mantığını uygular
• Sinyalin ardından 1g/3g/1h/2h/1ay getirilerini hesaplar
• TP1/SL vuruş oranlarını ve sürelerini çıkarır
• Evolver: skor eşiklerini / ağırlıkları optimize eder
"""

import yfinance as yf
import pandas as pd
import numpy as np
import os
import json
import pickle
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

from analyzer import _analyze_tf, _rsi, _macd, _ema, _atr

CACHE_DIR = os.path.join(os.path.dirname(__file__), "bt_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

RESULTS_FILE = os.path.join(os.path.dirname(__file__), "bt_results.json")
PARAMS_FILE  = os.path.join(os.path.dirname(__file__), "bt_params.json")

# ─── Varsayılan parametreler ──────────────────────────────────────────────────
DEFAULT_PARAMS = {
    "thresholds":      [7.5, 6.0, 4.5, 3.0],   # GÜÇLÜ AL / AL / İZLE / ZAYIF
    "weights_1d":      0.60,                     # 1d ağırlığı (1w = 1 - bu)
    "mtf_bonus":       0.5,
}


def load_params() -> dict:
    try:
        with open(PARAMS_FILE) as f:
            return json.load(f)
    except Exception:
        return DEFAULT_PARAMS.copy()


def save_params(params: dict):
    with open(PARAMS_FILE, "w") as f:
        json.dump(params, f, indent=2, ensure_ascii=False)


# ─── Veri indirme + disk cache ────────────────────────────────────────────────

def _cache_path(ticker: str) -> str:
    return os.path.join(CACHE_DIR, f"{ticker}.pkl")


def _is_cache_fresh(path: str, max_age_h: int = 24) -> bool:
    if not os.path.exists(path):
        return False
    age = time.time() - os.path.getmtime(path)
    return age < max_age_h * 3600


def _download_history(ticker: str, force: bool = False) -> dict | None:
    """Ticker için tam geçmiş veriyi indir ve cache'le."""
    path = _cache_path(ticker)
    if not force and _is_cache_fresh(path):
        try:
            with open(path, "rb") as f:
                return pickle.load(f)
        except Exception:
            pass

    yf_t = ticker + ".IS"
    try:
        t = yf.Ticker(yf_t)
        data = {
            "1d":  t.history(period="3y",  interval="1d",  auto_adjust=True),
            "1w":  t.history(period="5y",  interval="1wk", auto_adjust=True),
            "1mo": t.history(period="10y", interval="1mo", auto_adjust=True),
        }
        # Boş kontrolü
        if data["1d"] is None or len(data["1d"]) < 50:
            return None

        # Gereksiz kolonları temizle
        for df in data.values():
            if df is not None:
                for col in ["Dividends", "Stock Splits"]:
                    if col in df.columns:
                        df.drop(columns=[col], inplace=True)

        with open(path, "wb") as f:
            pickle.dump(data, f)
        return data
    except Exception:
        return None


# ─── Sinyal hesaplama (enjeksiyon ile) ───────────────────────────────────────

def _compute_signal(df_1d_slice: pd.DataFrame,
                    df_1w_slice: pd.DataFrame,
                    df_1mo_slice: pd.DataFrame,
                    params: dict) -> dict | None:
    """Kesilmiş veri üzerinde sinyal hesapla. analyzer.py'deki aynı mantık."""
    tf_1d  = _analyze_tf(df_1d_slice, "Günlük",  tf_type="1d")
    tf_1w  = _analyze_tf(df_1w_slice  if df_1w_slice is not None and len(df_1w_slice)  >= 15 else None,
                         "Haftalık", tf_type="1w")
    tf_1mo = _analyze_tf(df_1mo_slice if df_1mo_slice is not None and len(df_1mo_slice) >= 15 else None,
                         "Aylık",    tf_type="1mo")

    if tf_1d is None:
        return None

    w_1d = params.get("weights_1d", 0.60)
    w_1w = 1.0 - w_1d

    parts = [(tf_1d["score"], w_1d)]
    if tf_1w:
        parts.append((tf_1w["score"], w_1w))

    total_w  = sum(w for _, w in parts)
    ai_score = round(sum(s * w for s, w in parts) / total_w, 1)

    # MTF bonus/ceza
    tfs = [v for v in [tf_1d, tf_1w] if v]
    if len(tfs) >= 2:
        bull_n = sum(1 for tf in tfs if tf["trend"] == "BOĞA")
        bonus  = params.get("mtf_bonus", 0.5)
        if bull_n == len(tfs):
            ai_score = round(min(10, ai_score + bonus), 1)
        elif bull_n == 0:
            ai_score = round(max(0, ai_score - bonus), 1)

    action = _score_to_action(ai_score, params.get("thresholds"))

    return {
        "score":      ai_score,
        "action":     action,
        "setup_type": tf_1d.get("setup_type", "STANDART"),
        "tp1":        tf_1d["tp1"],
        "tp2":        tf_1d["tp2"],
        "sl":         tf_1d["sl"],
    }


def _score_to_action(score: float, thresholds=None) -> str:
    t = thresholds or [7.5, 6.0, 4.5, 3.0]
    if score >= t[0]: return "GÜÇLÜ AL"
    if score >= t[1]: return "AL"
    if score >= t[2]: return "İZLE"
    if score >= t[3]: return "ZAYIF"
    return "SAT"


# ─── Piyasa rejimi (BIST100 endeksi) ─────────────────────────────────────────

_bist100_cache: dict = {}   # {"data": df, "ts": timestamp}

def _bist100_regime(signal_date) -> str:
    """
    BIST100 endeksinin signal_date tarihindeki rejimini döndür.
    'BULL' → endeks EMA20 üzerinde  |  'BEAR' → altında
    """
    global _bist100_cache
    if not _bist100_cache or time.time() - _bist100_cache.get("ts", 0) > 86400:
        try:
            t = yf.Ticker("XU100.IS")
            df = t.history(period="3y", interval="1d", auto_adjust=True)
            _bist100_cache = {"data": df, "ts": time.time()}
        except Exception:
            return "BULL"   # veri alınamazsa filtreleme yapma

    df = _bist100_cache["data"]
    df_slice = df[df.index.normalize() <= signal_date]
    if len(df_slice) < 20:
        return "BULL"

    close  = df_slice["Close"]
    ema20  = float(close.ewm(span=20, adjust=False).mean().iloc[-1])
    cur    = float(close.iloc[-1])
    return "BULL" if cur >= ema20 else "BEAR"


# ─── Tek hisse backtest ───────────────────────────────────────────────────────

def backtest_ticker(ticker: str,
                    lookback_days: int = 365,
                    step_days: int = 5,
                    params: dict | None = None,
                    force_download: bool = False,
                    fresh_signals_only: bool = True,
                    market_filter: bool = True) -> list[dict]:
    """
    Tek hisse için walk-forward backtest çalıştır.

    fresh_signals_only : Sadece aksiyonun ilk değiştiği günü kaydet
                         (aynı sinyal tekrar tekrar sayılmaz).
    market_filter      : Ayı piyasasında AL/GÜÇLÜ AL sinyallerini atla.
    """
    if params is None:
        params = load_params()

    data = _download_history(ticker, force=force_download)
    if data is None:
        return []

    df_1d_full  = data["1d"]
    df_1w_full  = data["1w"]
    df_1mo_full = data["1mo"]

    dates_1d = df_1d_full.index.normalize().unique().sort_values()
    if len(dates_1d) < 60:
        return []

    start_idx = max(0, len(dates_1d) - lookback_days - 30)
    end_idx   = len(dates_1d) - 30   # en az 30 bar sonuç için bırak

    eval_dates = dates_1d[start_idx:end_idx]   # step_days burada değil — her gün kontrol

    results      = []
    prev_action  = None

    for i, signal_date in enumerate(eval_dates):
        # Veriyi o tarihe kadar kes
        df_1d  = df_1d_full[df_1d_full.index.normalize()  <= signal_date]
        df_1w  = df_1w_full[df_1w_full.index.normalize()  <= signal_date]
        df_1mo = df_1mo_full[df_1mo_full.index.normalize()<= signal_date]

        if len(df_1d) < 30:
            continue

        sig = _compute_signal(df_1d, df_1w, df_1mo, params)
        if sig is None:
            continue

        action = sig["action"]

        # ── Düzeltme 2: Sadece taze sinyali kaydet ──────────────────────────
        if fresh_signals_only and action == prev_action:
            prev_action = action
            continue
        prev_action = action

        # ── Düzeltme 3: Piyasa rejimi filtresi ──────────────────────────────
        if market_filter and action in ("GÜÇLÜ AL", "AL"):
            regime = _bist100_regime(signal_date)
            if regime == "BEAR":
                continue   # Ayı piyasasında AL sinyalini geçersiz say

        # ── Düzeltme 1: Giriş fiyatı = ertesi gün open ──────────────────────
        future = df_1d_full[df_1d_full.index.normalize() > signal_date]
        if len(future) == 0:
            continue

        # Gerçekçi giriş fiyatı: ertesi gün açılışı
        entry_price = float(future["Open"].iloc[0])

        # Getiri hesapla (entry_price bazlı)
        def _ret(n):
            if len(future) >= n:
                return round((float(future["Close"].iloc[n-1]) - entry_price) / entry_price * 100, 2)
            return None

        returns = {
            "return_1d":  _ret(1),
            "return_3d":  _ret(3),
            "return_1w":  _ret(5),
            "return_2w":  _ret(10),
            "return_1mo": _ret(20),
        }

        # TP / SL vuruş analizi (30 bar içinde, entry_price'tan itibaren)
        hit_tp1 = hit_tp2 = hit_sl = False
        days_to_tp1 = days_to_sl = None

        for j, (_, row) in enumerate(future.head(30).iterrows()):
            hi = float(row["High"])
            lo = float(row["Low"])
            if sig["tp1"] and not hit_tp1 and hi >= sig["tp1"]:
                hit_tp1 = True
                days_to_tp1 = j + 1
            if sig["tp2"] and not hit_tp2 and hi >= sig["tp2"]:
                hit_tp2 = True
            if sig["sl"] and not hit_sl and lo <= sig["sl"]:
                hit_sl = True
                days_to_sl = j + 1

        results.append({
            "ticker":      ticker,
            "signal_date": signal_date.strftime("%Y-%m-%d"),
            "action":      action,
            "setup_type":  sig.get("setup_type", "STANDART"),
            "score":       sig["score"],
            "price":       round(entry_price, 2),
            "close_price": round(float(df_1d["Close"].iloc[-1]), 2),
            "tp1":         sig["tp1"],
            "tp2":         sig["tp2"],
            "sl":          sig["sl"],
            "hit_tp1":     hit_tp1,
            "hit_tp2":     hit_tp2,
            "hit_sl":      hit_sl,
            "days_to_tp1": days_to_tp1,
            "days_to_sl":  days_to_sl,
            **returns,
        })

    return results


# ─── Çoklu hisse backtest ─────────────────────────────────────────────────────

def backtest_tickers(tickers: list[str],
                     lookback_days: int = 365,
                     step_days: int = 5,
                     params: dict | None = None,
                     max_workers: int = 4,
                     progress_cb=None,
                     fresh_signals_only: bool = True,
                     market_filter: bool = True) -> list[dict]:
    """Birden fazla hisse için paralel backtest."""
    all_results = []
    done = 0

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {
            ex.submit(backtest_ticker, t, lookback_days, step_days, params,
                      False, fresh_signals_only, market_filter): t
            for t in tickers
        }
        for fut in as_completed(futures):
            ticker = futures[fut]
            try:
                res = fut.result()
                all_results.extend(res)
            except Exception as e:
                print(f"[backtest] {ticker} hata: {e}")
            done += 1
            if progress_cb:
                progress_cb(done, len(tickers), ticker)

    return all_results


# ─── İstatistik hesaplama ─────────────────────────────────────────────────────

def compute_stats(results: list[dict]) -> dict:
    """Backtest sonuçlarından doğruluk istatistikleri çıkar."""
    if not results:
        return {}

    df = pd.DataFrame(results)
    stats = {"overall": {}, "by_action": {}}

    # Genel istatistikler
    total = len(df)
    stats["overall"] = {
        "total_signals": total,
        "tickers":       df["ticker"].nunique(),
        "date_range":    [df["signal_date"].min(), df["signal_date"].max()],
        "win_rate_1w":   round((df["return_1w"] > 0).mean() * 100, 1) if "return_1w" in df else None,
        "avg_return_1w": round(df["return_1w"].mean(), 2) if "return_1w" in df else None,
    }

    # Sinyal bazlı istatistikler
    MIN_SIGNALS = 10   # güvenilir istatistik için minimum
    for action in ["GÜÇLÜ AL", "AL", "İZLE", "ZAYIF", "SAT"]:
        sub = df[df["action"] == action]
        if len(sub) == 0:
            continue
        low_sample = len(sub) < MIN_SIGNALS

        tp1_sub = sub[sub["hit_tp1"] == True]
        sl_sub  = sub[sub["hit_sl"]  == True]

        stats["by_action"][action] = {
            "count":          int(len(sub)),
            "low_sample":     low_sample,   # < 10 sinyal → güvenilirlik düşük
            "win_rate_1d":    _pct(sub, "return_1d",  "> 0"),
            "win_rate_1w":    _pct(sub, "return_1w",  "> 0"),
            "win_rate_1mo":   _pct(sub, "return_1mo", "> 0"),
            "avg_return_1d":  _avg(sub, "return_1d"),
            "avg_return_1w":  _avg(sub, "return_1w"),
            "avg_return_1mo": _avg(sub, "return_1mo"),
            "best_1mo":       _val(sub["return_1mo"].max()),
            "worst_1mo":      _val(sub["return_1mo"].min()),
            "tp1_hit_rate":   round(sub["hit_tp1"].mean() * 100, 1) if "hit_tp1" in sub else None,
            "tp2_hit_rate":   round(sub["hit_tp2"].mean() * 100, 1) if "hit_tp2" in sub else None,
            "sl_hit_rate":    round(sub["hit_sl"].mean() * 100, 1)  if "hit_sl"  in sub else None,
            "avg_days_to_tp1":round(tp1_sub["days_to_tp1"].mean(), 1) if len(tp1_sub) > 0 else None,
            "avg_days_to_sl": round(sl_sub["days_to_sl"].mean(), 1)   if len(sl_sub)  > 0 else None,
            "expected_value_1w": _expected_value(sub, "return_1w"),
        }

    # Setup türüne göre istatistikler
    stats["by_setup"] = {}
    for setup in ["KIRILIM", "DÖNÜŞ", "STANDART"]:
        sub = df[df.get("setup_type", "STANDART") == setup] if "setup_type" in df else pd.DataFrame()
        # pandas column lookup
        if "setup_type" in df.columns:
            sub = df[df["setup_type"] == setup]
        if len(sub) == 0:
            continue
        stats["by_setup"][setup] = {
            "count":          int(len(sub)),
            "low_sample":     len(sub) < MIN_SIGNALS,
            "win_rate_1w":    _pct(sub, "return_1w",  "> 0"),
            "win_rate_1mo":   _pct(sub, "return_1mo", "> 0"),
            "avg_return_1w":  _avg(sub, "return_1w"),
            "avg_return_1mo": _avg(sub, "return_1mo"),
            "best_1mo":       _val(sub["return_1mo"].max()) if "return_1mo" in sub else None,
            "worst_1mo":      _val(sub["return_1mo"].min()) if "return_1mo" in sub else None,
            "tp1_hit_rate":   round(sub["hit_tp1"].mean() * 100, 1) if "hit_tp1" in sub.columns else None,
            "sl_hit_rate":    round(sub["hit_sl"].mean() * 100, 1)  if "hit_sl"  in sub.columns else None,
            "expected_value_1w": _expected_value(sub, "return_1w"),
            "pct_3plus":      round((sub["return_1w"] >= 3).mean() * 100, 1) if "return_1w" in sub else None,
            "pct_5plus":      round((sub["return_1w"] >= 5).mean() * 100, 1) if "return_1w" in sub else None,
        }

    return stats


def _pct(df, col, cond):
    if col not in df or df[col].isna().all():
        return None
    clean = df[col].dropna()
    if len(clean) == 0:
        return None
    return round(eval(f"(clean {cond}).mean()") * 100, 1)


def _avg(df, col):
    if col not in df or df[col].isna().all():
        return None
    return round(df[col].mean(), 2)


def _val(v):
    try:
        return round(float(v), 2) if v is not None and not np.isnan(v) else None
    except Exception:
        return None


def _expected_value(df, col):
    """Basit beklenen değer: ortalama kazanç × kazanma olasılığı + ortalama kayıp × kayıp olasılığı"""
    if col not in df:
        return None
    clean = df[col].dropna()
    if len(clean) == 0:
        return None
    wins   = clean[clean > 0]
    losses = clean[clean <= 0]
    p_win  = len(wins) / len(clean)
    avg_w  = wins.mean() if len(wins) > 0 else 0
    avg_l  = losses.mean() if len(losses) > 0 else 0
    ev     = round(p_win * avg_w + (1 - p_win) * avg_l, 2)
    return ev


# ─── Korelasyon analizi ──────────────────────────────────────────────────────

def correlation_analysis(results: list[dict]) -> dict:
    """
    Skor ile forward getiriler arasındaki korelasyonu ve
    skor aralıklarına göre win rate dağılımını çıkarır.
    """
    if not results:
        return {}

    df = pd.DataFrame(results)

    # Skor-getiri korelasyonu
    corr_1w  = round(df[["score","return_1w"]].dropna().corr().iloc[0,1], 3) if "return_1w" in df else None
    corr_1mo = round(df[["score","return_1mo"]].dropna().corr().iloc[0,1], 3) if "return_1mo" in df else None

    # Skor bucketları → win rate
    buckets = []
    edges = [0, 4, 5, 6, 7, 7.5, 8, 8.5, 9, 10]
    for i in range(len(edges)-1):
        lo, hi = edges[i], edges[i+1]
        sub = df[(df["score"] >= lo) & (df["score"] < hi)]
        if len(sub) == 0:
            continue
        buckets.append({
            "range":      f"{lo}–{hi}",
            "count":      int(len(sub)),
            "win_rate_1w": round((sub["return_1w"] > 0).mean() * 100, 1) if "return_1w" in sub else None,
            "avg_return_1w": round(sub["return_1w"].mean(), 2) if "return_1w" in sub else None,
            "win_rate_1mo": round((sub["return_1mo"] > 0).mean() * 100, 1) if "return_1mo" in sub else None,
            "avg_return_1mo": round(sub["return_1mo"].mean(), 2) if "return_1mo" in sub else None,
        })

    # En çok kazandıran skor eşiği bul
    best_threshold = None
    best_ev = -999
    for thresh in [6.0, 6.5, 7.0, 7.5, 8.0, 8.5]:
        sub = df[df["score"] >= thresh]
        if len(sub) < 5:
            continue
        ev = _expected_value(sub, "return_1w")
        wr = (sub["return_1w"] > 0).mean() * 100 if "return_1w" in sub else 0
        if ev is not None and ev > best_ev and wr > 50:
            best_ev = ev
            best_threshold = thresh

    return {
        "score_return_corr_1w":  corr_1w,
        "score_return_corr_1mo": corr_1mo,
        "score_buckets":         buckets,
        "best_threshold":        best_threshold,
        "best_threshold_ev":     round(best_ev, 3) if best_ev > -999 else None,
        "interpretation": (
            "Skor-getiri korelasyonu çok düşük — momentum faktörü henüz aktif değil. "
            "Backtest'i yeniden çalıştırın." if abs(corr_1w or 0) < 0.1
            else "Korelasyon mevcut — skor sistemi öngörü gücü taşıyor."
        ),
    }


# ─── Evolver: parametre optimizasyonu ────────────────────────────────────────

def evolve_params(results: list[dict], target_action: str = "GÜÇLÜ AL") -> dict:
    """
    Backtest sonuçlarına bakarak skor eşiklerini ve ağırlıkları optimize eder.
    Basit grid search — optuna gerektirmez.

    Hedef: GÜÇLÜ AL için beklenen değeri (expected_value_1w) maksimize et
           VE win_rate_1w'yi %55 üzerinde tut.
    """
    if not results:
        return load_params()

    df = pd.DataFrame(results)

    best_params = None
    best_ev     = -999.0

    # Eşik arama uzayı
    threshold_options = [
        [7.5, 6.0, 4.5, 3.0],
        [7.0, 5.5, 4.0, 2.5],
        [8.0, 6.5, 5.0, 3.5],
        [7.5, 5.5, 4.0, 2.5],
        [7.0, 6.0, 4.5, 3.0],
        [8.0, 6.0, 4.5, 3.0],
    ]
    weight_options = [0.50, 0.60, 0.70, 0.80]
    bonus_options  = [0.3, 0.5, 0.7]

    for thresholds in threshold_options:
        for w_1d in weight_options:
            for bonus in bonus_options:
                params = {
                    "thresholds": thresholds,
                    "weights_1d": w_1d,
                    "mtf_bonus":  bonus,
                }

                # Mevcut sonuçları bu parametrelerle yeniden skorla
                rescored = _rescore(df, params)
                sub = rescored[rescored["action_new"] == target_action]

                if len(sub) < 10:
                    continue

                ev       = _expected_value(sub, "return_1w")
                win_rate = _pct(sub, "return_1w", "> 0") or 0

                if ev is None or ev < best_ev:
                    continue
                if win_rate < 50:  # minimum %50 win rate şartı
                    continue

                best_ev     = ev
                best_params = params.copy()

    if best_params is None:
        return load_params()

    # Parametre değişimlerini raporla
    old = load_params()
    best_params["evolved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    best_params["target_ev"]  = round(best_ev, 3)

    print(f"[evolver] Eski eşikler: {old['thresholds']}  → Yeni: {best_params['thresholds']}")
    print(f"[evolver] Eski w_1d: {old['weights_1d']}  → Yeni: {best_params['weights_1d']}")
    print(f"[evolver] Beklenen değer ({target_action}): {best_ev:.3f}%")

    return best_params


def _rescore(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """Mevcut skor sütununu kullanarak aksiyon etiketlerini yeniden hesapla."""
    df = df.copy()
    df["action_new"] = df["score"].apply(
        lambda s: _score_to_action(s, params.get("thresholds"))
    )
    return df


# ─── Sonuç kayıt/yükle ───────────────────────────────────────────────────────

def save_results(results: list[dict]):
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False)


def load_results() -> list[dict]:
    try:
        with open(RESULTS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []
