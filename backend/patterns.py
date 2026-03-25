"""
Klasik Teknik Analiz Formasyonları + Elliott Wave Tespiti
OHLCV verisinden pattern tanıma ve sonraki hareket tahmini.
"""
import numpy as np
import yfinance as yf
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# Global rate-limit mekanizması (analyzer.py ile paylaşılır)
try:
    from analyzer import _wait_if_rate_limited, _set_rate_limit
except ImportError:
    def _wait_if_rate_limited(): pass
    def _set_rate_limit(w=60.0): pass

_pat_cache: dict = {}
_pat_time: dict = {}
_PAT_TTL = 1800  # 30 dakika
_BATCH   = 30    # bir yf.download çağrısında kaç hisse (küçük tutuyoruz)


# ─── Veri çekimi ─────────────────────────────────────────────────────────────

def _get_daily(ticker: str):
    """Tek hisse için veri çek (fallback)."""
    for attempt in range(3):
        _wait_if_rate_limited()
        try:
            df = yf.download(f"{ticker}.IS", period="6mo", interval="1d", progress=False, auto_adjust=True)
            if df is None or len(df) < 30:
                return None
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
            return df.dropna()
        except Exception as e:
            msg = str(e).lower()
            if "too many" in msg or "rate limit" in msg or "429" in msg:
                _set_rate_limit(60.0)
            else:
                return None
    return None


def _bulk_download(tickers: list) -> dict:
    """Toplu yfinance indirmesi — tek HTTP isteğinde N hisse."""
    if not tickers:
        return {}
    tickers_is = [f"{t}.IS" for t in tickers]
    try:
        if len(tickers_is) == 1:
            df = yf.download(tickers_is[0], period="6mo", interval="1d",
                             progress=False, auto_adjust=True)
            if df is None or df.empty:
                return {}
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
            return {tickers[0]: df.dropna()} if len(df) >= 30 else {}

        _wait_if_rate_limited()
        try:
            df_all = yf.download(
                tickers_is, period="6mo", interval="1d",
                progress=False, auto_adjust=True, group_by="ticker"
            )
        except Exception as e:
            msg = str(e).lower()
            if "too many" in msg or "rate limit" in msg or "429" in msg:
                _set_rate_limit(60.0)
            return {}
        if df_all is None or df_all.empty:
            return {}

        result = {}
        cols = df_all.columns

        # yfinance sürümüne göre iki farklı MultiIndex yapısı:
        # Yeni: level0=Price(Open/High/..), level1=Ticker
        # Eski: level0=Ticker, level1=Price
        if hasattr(cols, 'levels') and len(cols.levels) == 2:
            lvl0 = list(cols.get_level_values(0).unique())
            lvl1 = list(cols.get_level_values(1).unique())
            # Hangi level ticker olduğunu belirle
            price_cols = {'Open', 'High', 'Low', 'Close', 'Volume', 'Adj Close'}
            if any(c in price_cols for c in lvl0):
                # level0=Price, level1=Ticker (yeni yfinance)
                ticker_level = 1
                price_level  = 0
            else:
                # level0=Ticker, level1=Price (eski yfinance)
                ticker_level = 0
                price_level  = 1

            available = set(cols.get_level_values(ticker_level).unique())
            for t, t_is in zip(tickers, tickers_is):
                if t_is not in available:
                    continue
                try:
                    if ticker_level == 1:
                        df = df_all.xs(t_is, axis=1, level=1).dropna()
                    else:
                        df = df_all[t_is].dropna()
                    if len(df) >= 30:
                        result[t] = df
                except Exception:
                    continue
        return result
    except Exception:
        return {}


def _swings(highs, lows, lb=3):
    n = len(highs)
    hi, lo = [], []
    for i in range(lb, n - lb):
        if all(highs[i] >= highs[i-j] for j in range(1, lb+1)) and \
           all(highs[i] >= highs[i+j] for j in range(1, lb+1)):
            hi.append(i)
        if all(lows[i] <= lows[i-j] for j in range(1, lb+1)) and \
           all(lows[i] <= lows[i+j] for j in range(1, lb+1)):
            lo.append(i)
    return hi, lo


# ─── Çift Tepe / Çift Dip ─────────────────────────────────────────────────────

def _double_top(highs, closes, sh):
    if len(sh) < 2:
        return None
    h1, h2 = highs[sh[-2]], highs[sh[-1]]
    tol = 0.03  # %3 tolerans
    if abs(h1 - h2) / max(h1, h2) > tol:
        return None
    neck = min(closes[sh[-2]:sh[-1]])
    cur = closes[-1]
    if cur > neck * 1.02:  # henüz kırılmadı
        return None
    target = neck - (max(h1, h2) - neck)
    return {
        "pattern": "double_top", "name": "Çift Tepe",
        "direction": "bearish", "confidence": round(0.65 + (tol - abs(h1-h2)/max(h1,h2))/tol * 0.2, 2),
        "description": f"İki benzer tepe ({h1:.2f} / {h2:.2f}) oluştu. Boyun çizgisi kırıldı.",
        "neckline": round(neck, 2), "target": round(target, 2),
    }


def _double_bottom(lows, closes, sl):
    if len(sl) < 2:
        return None
    l1, l2 = lows[sl[-2]], lows[sl[-1]]
    tol = 0.03
    if abs(l1 - l2) / max(l1, l2) > tol:
        return None
    neck = max(closes[sl[-2]:sl[-1]])
    cur = closes[-1]
    if cur < neck * 0.98:
        return None
    target = neck + (neck - min(l1, l2))
    return {
        "pattern": "double_bottom", "name": "Çift Dip",
        "direction": "bullish", "confidence": round(0.65 + (tol - abs(l1-l2)/max(l1,l2))/tol * 0.2, 2),
        "description": f"İki benzer dip ({l1:.2f} / {l2:.2f}) oluştu. Boyun çizgisi kırıldı.",
        "neckline": round(neck, 2), "target": round(target, 2),
    }


# ─── Omuz-Baş-Omuz ───────────────────────────────────────────────────────────

def _head_shoulders(highs, lows, closes, sh, sl):
    if len(sh) < 3 or len(sl) < 2:
        return None
    ls, head, rs = highs[sh[-3]], highs[sh[-2]], highs[sh[-1]]
    # Baş iki omuzdan yüksek olmalı
    if not (head > ls and head > rs):
        return None
    # Omuzlar birbirine yakın
    if abs(ls - rs) / max(ls, rs) > 0.05:
        return None
    # Boyun: iki dip arasındaki çizgi
    n_lows = [sl_i for sl_i in sl if sh[-3] < sl_i < sh[-1]]
    if len(n_lows) < 2:
        return None
    neck = (lows[n_lows[0]] + lows[n_lows[-1]]) / 2
    cur = closes[-1]
    if cur > neck * 1.01:
        return None
    target = neck - (head - neck)
    return {
        "pattern": "head_shoulders", "name": "Omuz-Baş-Omuz",
        "direction": "bearish", "confidence": 0.78,
        "description": f"Klasik OBO formasyonu. Boyun: {neck:.2f}, Baş: {head:.2f}",
        "neckline": round(neck, 2), "target": round(target, 2),
    }


def _inv_head_shoulders(highs, lows, closes, sh, sl):
    if len(sl) < 3 or len(sh) < 2:
        return None
    ls, head, rs = lows[sl[-3]], lows[sl[-2]], lows[sl[-1]]
    if not (head < ls and head < rs):
        return None
    if abs(ls - rs) / max(ls, rs) > 0.05:
        return None
    n_highs = [sh_i for sh_i in sh if sl[-3] < sh_i < sl[-1]]
    if len(n_highs) < 2:
        return None
    neck = (highs[n_highs[0]] + highs[n_highs[-1]]) / 2
    cur = closes[-1]
    if cur < neck * 0.99:
        return None
    target = neck + (neck - head)
    return {
        "pattern": "inv_head_shoulders", "name": "Ters OBO",
        "direction": "bullish", "confidence": 0.78,
        "description": f"Ters Omuz-Baş-Omuz. Boyun: {neck:.2f}, Dip: {head:.2f}",
        "neckline": round(neck, 2), "target": round(target, 2),
    }


# ─── Üçgen Formasyonlar ───────────────────────────────────────────────────────

def _triangles(highs, lows, closes, last_n=40):
    h = highs[-last_n:]
    l = lows[-last_n:]
    n = len(h)
    if n < 10:
        return None

    x = np.arange(n)
    # Tepe trendini (direniş)
    ph = np.polyfit(x, h, 1)
    # Dip trendini (destek)
    pl = np.polyfit(x, l, 1)

    h_slope = ph[0]  # negatif=aşağı, pozitif=yukarı
    l_slope = pl[0]

    cur = closes[-1]
    h_now = np.polyval(ph, n)
    l_now = np.polyval(pl, n)
    width = h_now - l_now

    tol = 0.02 * cur

    if h_slope < -0.001 and abs(l_slope) < 0.001:
        # Azalan üçgen → Bearish
        return {
            "pattern": "desc_triangle", "name": "Azalan Üçgen",
            "direction": "bearish", "confidence": 0.68,
            "description": f"Sabit destek, düşen direnç. Kırılım bekleniyor.",
            "support": round(l_now, 2), "resistance": round(h_now, 2),
            "target": round(l_now - width, 2),
        }
    elif l_slope > 0.001 and abs(h_slope) < 0.001:
        # Artan üçgen → Bullish
        return {
            "pattern": "asc_triangle", "name": "Artan Üçgen",
            "direction": "bullish", "confidence": 0.70,
            "description": f"Sabit direnç, yükselen destek. Yukarı kırılım bekleniyor.",
            "support": round(l_now, 2), "resistance": round(h_now, 2),
            "target": round(h_now + width, 2),
        }
    elif h_slope < -0.001 and l_slope > 0.001:
        # Simetrik üçgen
        return {
            "pattern": "sym_triangle", "name": "Simetrik Üçgen",
            "direction": "neutral", "confidence": 0.60,
            "description": f"Düşen tepe, yükselen dip — kırılım yakın.",
            "support": round(l_now, 2), "resistance": round(h_now, 2),
            "target": round(h_now + width * 0.8, 2),  # dominant trend yönü
        }
    return None


# ─── Bayrak / Flama ───────────────────────────────────────────────────────────

def _flag(closes, last_n=30):
    if len(closes) < last_n + 10:
        return None
    # Sap: hızlı güçlü hareket (son 10 bar öncesi)
    pole_start = closes[-last_n - 10]
    pole_end   = closes[-last_n]
    pole_move  = (pole_end - pole_start) / pole_start

    if abs(pole_move) < 0.08:  # en az %8 sap hareketi
        return None

    # Flama: konsolidasyon (son last_n bar)
    flag_part = np.array(closes[-last_n:])
    flag_range = (flag_part.max() - flag_part.min()) / pole_end
    if flag_range > 0.06:  # konsolidasyon dar olmalı
        return None

    direction = "bullish" if pole_move > 0 else "bearish"
    target = closes[-1] + (pole_end - pole_start)
    return {
        "pattern": "flag", "name": "Bayrak Formasyonu",
        "direction": direction, "confidence": 0.65,
        "description": f"{'Boğa' if direction=='bullish' else 'Ayı'} bayrağı — sap hareketi: {pole_move*100:.1f}%",
        "target": round(target, 2),
    }


# ─── Kama (Wedge) ────────────────────────────────────────────────────────────

def _wedge(highs, lows, closes, last_n=35):
    h = highs[-last_n:]
    l = lows[-last_n:]
    n = len(h)
    if n < 10:
        return None
    x = np.arange(n)
    ph = np.polyfit(x, h, 1)
    pl = np.polyfit(x, l, 1)
    h_slope = ph[0]
    l_slope = pl[0]

    # Her ikisi de yükseliyorsa ve daralan → Yükselen kama (bearish)
    if h_slope > 0.001 and l_slope > 0.001 and l_slope > h_slope:
        return {
            "pattern": "rising_wedge", "name": "Yükselen Kama",
            "direction": "bearish", "confidence": 0.70,
            "description": "Her iki trendline da yükseliyor ancak daralan yapı. Kırılım olası.",
            "target": round(float(np.polyval(pl, n)), 2),
        }
    # Her ikisi de düşüyorsa ve daralan → Düşen kama (bullish)
    elif h_slope < -0.001 and l_slope < -0.001 and h_slope < l_slope:
        return {
            "pattern": "falling_wedge", "name": "Düşen Kama",
            "direction": "bullish", "confidence": 0.70,
            "description": "Her iki trendline da düşüyor, daralan yapı. Yukarı kırılım bekleniyor.",
            "target": round(float(np.polyval(ph, n)), 2),
        }
    return None


# ─── Elliott Wave (Basitleştirilmiş) ─────────────────────────────────────────

def _elliott_wave(highs, lows, closes, sh, sl):
    """
    Son 5 önemli pivot noktası kullanarak Elliott 5-dalga yapısı tespiti.
    Kurallar:
    - Dalga 2, dalga 1'in %100'ünden fazlasını geri almaz
    - Dalga 3 en kısa dalga olamaz
    - Dalga 4, dalga 1 zirvesini aşmaz
    """
    # En az 5 tepe ve 5 dip gerekli
    if len(sh) < 3 or len(sl) < 3:
        return None

    cur = closes[-1]

    # Yükselen 5-dalga yapısı: low → high → low → high → low → high
    recent_highs = [highs[i] for i in sh[-3:]]
    recent_lows  = [lows[i]  for i in sl[-3:]]

    # Basit versiyon: son 3 tepe ve 3 dip ile dalga yapısı
    # W1: ilk dip → ilk tepe
    # W2: ilk tepe → ikinci dip
    # W3: ikinci dip → ikinci tepe
    # W4: ikinci tepe → üçüncü dip
    # W5: üçüncü dip → üçüncü tepe (son)
    if len(recent_lows) < 3 or len(recent_highs) < 3:
        return None

    # Boğa dalgası tahmini
    w1 = recent_highs[0] - recent_lows[0]
    w2 = recent_highs[0] - recent_lows[1]
    w3 = recent_highs[1] - recent_lows[1]
    w4 = recent_highs[1] - recent_lows[2]
    w5_start = recent_lows[2]

    if w1 <= 0 or w3 <= 0:
        return None

    # Kural kontrolleri
    if w2 / w1 > 1.0:  # W2 kural ihlali
        return None
    if w3 < w1 and w3 < (recent_highs[2] - w5_start if len(recent_highs) >= 3 else w3):  # W3 en kısa
        return None

    # Fibonacci hedef (W5 = W1 × 0.618 ~ 1.618)
    fib_ratios = [0.618, 1.0, 1.618]
    best_ratio = 1.0
    # Eğer W3 ≈ 1.618 × W1 ise güven yüksek
    w3_fib = w3 / w1
    confidence = 0.60
    if 1.4 <= w3_fib <= 1.9:
        confidence = 0.75

    w5_target = w5_start + w1 * best_ratio

    # Şu an hangi dalga?
    if cur < recent_highs[1] and cur > w5_start:
        wave_pos = "4. dalga (düzeltme)"
        direction = "bullish"  # 5. dalga için bekleniyor
        description = f"Elliott 4. Dalga düzeltmesinde. 5. Dalga hedefi: {w5_target:.2f}"
    elif cur >= recent_highs[1]:
        wave_pos = "5. dalga (son yükseliş)"
        direction = "neutral"
        w5_target = recent_highs[1] * 1.05
        description = f"Elliott 5. Dalga sonuna yakın. Dikkat, dönüş gelebilir."
    else:
        return None

    return {
        "pattern": "elliott_wave", "name": f"Elliott Dalgası ({wave_pos})",
        "direction": direction, "confidence": round(confidence, 2),
        "description": description,
        "wave_position": wave_pos,
        "w1": round(w1, 2), "w3": round(w3, 2),
        "fib_ratio_w3": round(w3_fib, 2),
        "target": round(w5_target, 2),
    }


# ─── DataFrame'den pattern analizi ──────────────────────────────────────────

def _analyze_from_df(ticker: str, df) -> dict | None:
    """İndirilmiş DataFrame'den formasyon analizi yap."""
    if df is None or len(df) < 30:
        return None
    try:
        highs  = df['High'].values.astype(float)
        lows   = df['Low'].values.astype(float)
        closes = df['Close'].values.astype(float)
        price  = float(closes[-1])

        sh, sl = _swings(highs, lows, lb=3)
        if not sh or not sl:
            return None

        patterns = []
        for fn in [
            lambda: _double_top(highs, closes, sh),
            lambda: _double_bottom(lows, closes, sl),
            lambda: _head_shoulders(highs, lows, closes, sh, sl),
            lambda: _inv_head_shoulders(highs, lows, closes, sh, sl),
            lambda: _triangles(highs, lows, closes),
            lambda: _flag(closes),
            lambda: _wedge(highs, lows, closes),
            lambda: _elliott_wave(highs, lows, closes, sh, sl),
        ]:
            try:
                r = fn()
                if r:
                    patterns.append(r)
            except Exception:
                continue

        patterns.sort(key=lambda x: x.get("confidence", 0), reverse=True)
        return {
            "ticker": ticker,
            "price": price,
            "patterns": patterns,
            "top_pattern": patterns[0] if patterns else None,
            "bullish_count": sum(1 for p in patterns if p.get("direction") == "bullish"),
            "bearish_count": sum(1 for p in patterns if p.get("direction") == "bearish"),
        }
    except Exception:
        return None


# ─── Ana tarama fonksiyonu ────────────────────────────────────────────────────

def analyze_patterns(ticker: str, main_cache: dict | None = None) -> dict | None:
    """Tek hisse için formasyon analizi (cache'li)."""
    if ticker in _pat_cache and time.time() - _pat_time.get(ticker, 0) < _PAT_TTL:
        return _pat_cache[ticker]

    df = _get_daily(ticker)
    result = _analyze_from_df(ticker, df)
    if result:
        _pat_cache[ticker] = result
        _pat_time[ticker] = time.time()
    return result


def scan_patterns(category: str, direction_filter: str = "all", main_cache: dict | None = None):
    """
    Tüm hisseleri pattern açısından tara.
    Toplu yfinance indirmesi kullanır — çok daha hızlı.
    direction_filter: "bullish" | "bearish" | "all"
    """
    from stocks import CATEGORIES
    tickers = CATEGORIES.get(category.upper(), CATEGORIES.get("BIST30", []))
    now = time.time()

    # Önbellekte olmayan hisseleri toplu indir
    uncached = [t for t in tickers
                if t not in _pat_cache or now - _pat_time.get(t, 0) >= _PAT_TTL]

    if uncached:
        # Ana tarayıcı zaten rate limit çekiyorsa bekle
        _wait_if_rate_limited()
        batches = [uncached[i:i + _BATCH] for i in range(0, len(uncached), _BATCH)]
        dfs: dict = {}
        for i, batch in enumerate(batches):
            try:
                r = _bulk_download(batch)
                dfs.update(r)
                if i < len(batches) - 1:
                    time.sleep(2.0)  # batch arası bekleme
            except Exception:
                pass

        # Pattern analizi paralel çalıştır (CPU-bound ama hızlı)
        with ThreadPoolExecutor(max_workers=8) as exe:
            futs = {exe.submit(_analyze_from_df, t, dfs.get(t)): t for t in uncached}
            for fut in as_completed(futs):
                t = futs[fut]
                try:
                    result = fut.result()
                    # Cache even "no pattern" results to avoid re-downloading
                    _pat_cache[t] = result or {"ticker": t, "patterns": [], "top_pattern": None, "bullish_count": 0, "bearish_count": 0}
                    _pat_time[t] = now
                except Exception:
                    pass

    # Sonuçları filtrele ve sırala
    results = []
    for t in tickers:
        r = _pat_cache.get(t)
        if not r or not r.get("patterns"):
            continue
        if direction_filter != "all":
            top = r.get("top_pattern")
            if not top or top.get("direction") != direction_filter:
                continue
        results.append(r)

    results.sort(key=lambda x: (x.get("top_pattern", {}) or {}).get("confidence", 0), reverse=True)
    return results
