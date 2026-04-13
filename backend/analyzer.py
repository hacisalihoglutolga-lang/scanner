"""
Kapsamlı BİST Teknik Analiz Motoru — Spot İşlem Odaklı
Çok zaman dilimli: 4 Saatlik / Günlük / Haftalık
"""
import yfinance as yf
import pandas as pd
import numpy as np
import warnings
import time
import random
import threading
import socket
warnings.filterwarnings("ignore")

# Her socket işlemi için max 12s — asılı kalan bağlantıları keser
socket.setdefaulttimeout(12)

# yfinance 1.x kendi session'ını yönetiyor
_yf_session = None

# ─── Global Rate-Limit Bekleme ───────────────────────────────────────────────
_rl_lock   = threading.Lock()
_rl_until  = 0.0          # Unix timestamp

class _RateLimited(Exception):
    pass

def _check_rate_limit():
    """Rate limit aktifse hemen exception — thread'i uyutma."""
    if _rl_until > time.time():
        raise _RateLimited("rate-limited")

def _set_rate_limit(wait_sec: float = 45.0):
    """Rate limit algılandı."""
    global _rl_until
    with _rl_lock:
        new_until = time.time() + wait_sec
        if new_until > _rl_until:
            _rl_until = new_until


def _yf_history(ticker_obj, **kwargs):
    """yfinance history çağrısını rate limit'e karşı sarmalar."""
    _check_rate_limit()
    try:
        df = ticker_obj.history(**kwargs)
        if df is not None and not df.empty:
            return df
        return df
    except _RateLimited:
        raise
    except Exception as e:
        msg = str(e).lower()
        if "too many requests" in msg or "rate limit" in msg or "429" in msg:
            _set_rate_limit(45.0)
            raise _RateLimited("rate-limited")
        raise


# ─── Temel Göstergeler ────────────────────────────────────────────────────────

def _rsi(c, p=14):
    d = c.diff()
    g = d.clip(lower=0).rolling(p).mean()
    l = (-d.clip(upper=0)).rolling(p).mean()
    return 100 - 100 / (1 + g / l.replace(0, np.nan))

def _macd(c, f=12, s=26, sig=9):
    ef = c.ewm(span=f, adjust=False).mean()
    es = c.ewm(span=s, adjust=False).mean()
    m = ef - es
    si = m.ewm(span=sig, adjust=False).mean()
    return m, si, m - si

def _ema(c, p):
    return c.ewm(span=p, adjust=False).mean()

def _atr(h, l, c, p=14):
    tr = pd.concat([(h-l), (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(p).mean()

def _bollinger(c, p=20, std=2.0):
    ma = c.rolling(p).mean()
    s  = c.rolling(p).std(ddof=0)
    return float(ma.iloc[-1]), float((ma + std*s).iloc[-1]), float((ma - std*s).iloc[-1])


# ─── Swing Noktaları ──────────────────────────────────────────────────────────

def _swings(df, lb=3):
    h, l = df['High'].values, df['Low'].values
    hi, lo = [], []
    for i in range(lb, len(df)-lb):
        if all(h[i] >= h[i-j] for j in range(1,lb+1)) and all(h[i] >= h[i+j] for j in range(1,lb+1)):
            hi.append(i)
        if all(l[i] <= l[i-j] for j in range(1,lb+1)) and all(l[i] <= l[i+j] for j in range(1,lb+1)):
            lo.append(i)
    return hi, lo


# ─── Piyasa Yapısı (HH / HL / LH / LL) ──────────────────────────────────────

def _market_structure(df, sh, sl):
    if len(sh) < 2 or len(sl) < 2:
        return "YATAY", None, None, None, None
    h, l = df['High'].values, df['Low'].values
    hh1, hh2 = round(h[sh[-1]], 2), round(h[sh[-2]], 2)
    ll1, ll2 = round(l[sl[-1]], 2), round(l[sl[-2]], 2)
    if hh1 > hh2 and ll1 > ll2:
        return "YUKSELIS", hh1, ll1, None, None
    elif hh1 < hh2 and ll1 < ll2:
        return "DUSUS", None, None, hh1, ll1
    else:
        return "YATAY", None, None, None, None


# ─── Destek / Direnç Seviyeleri ───────────────────────────────────────────────

def _sr_levels(df, sh, sl, n=4, tol=0.015):
    prices = [float(df['High'].iloc[i]) for i in sh[-10:]] + \
             [float(df['Low'].iloc[i])  for i in sl[-10:]]
    prices.sort()
    clusters = []
    i = 0
    while i < len(prices):
        grp = [prices[i]]
        j = i+1
        while j < len(prices) and prices[j] <= prices[i]*(1+tol):
            grp.append(prices[j]); j += 1
        clusters.append((round(sum(grp)/len(grp),2), len(grp)))
        i = j
    cur = float(df['Close'].iloc[-1])
    sup = sorted([(v,t) for v,t in clusters if v < cur], key=lambda x: x[0], reverse=True)
    res = sorted([(v,t) for v,t in clusters if v > cur], key=lambda x: x[0])
    return [v for v,_ in sup[:n]], [v for v,_ in res[:n]]


# ─── Order Blocks ─────────────────────────────────────────────────────────────

def _order_blocks(df, lb=80):
    o,h,l,c = df['Open'].values, df['High'].values, df['Low'].values, df['Close'].values
    idx = df.index
    cur = c[-1]
    bull = bear = None
    for i in range(len(df)-3, max(1,len(df)-lb), -1):
        if bull is None and c[i] < o[i]:
            fmax = h[i+1:min(i+6,len(df))].max()
            if fmax > h[i]*1.003 and cur > l[i]:
                bull = {"price": round((h[i]+l[i])/2,2), "high": round(h[i],2),
                        "low": round(l[i],2), "date": idx[i].strftime("%d/%m %H:%M")}
        if bear is None and c[i] > o[i]:
            fmin = l[i+1:min(i+6,len(df))].min()
            if fmin < l[i]*0.997 and cur < h[i]:
                bear = {"price": round((h[i]+l[i])/2,2), "high": round(h[i],2),
                        "low": round(l[i],2), "date": idx[i].strftime("%d/%m %H:%M")}
        if bull and bear: break
    return bull, bear


def _order_blocks_multi(df, lb=120, max_each=3):
    """Multiple bullish + bearish order blocks + supply/demand zones."""
    o,h,l,c = df['Open'].values, df['High'].values, df['Low'].values, df['Close'].values
    idx = df.index
    cur = c[-1]
    bulls, bears = [], []
    for i in range(len(df)-3, max(1,len(df)-lb), -1):
        # Bullish OB: bearish candle followed by strong bullish move (demand zone)
        if len(bulls) < max_each and c[i] < o[i]:
            fmax = h[i+1:min(i+6,len(df))].max()
            if fmax > h[i]*1.003 and cur > l[i]:
                # strength: how strong was the subsequent move
                strength = round((fmax - h[i]) / max(h[i]-l[i], 0.001) * 100, 1)
                bulls.append({
                    "price": round((h[i]+l[i])/2, 2),
                    "high":  round(h[i], 2),
                    "low":   round(l[i], 2),
                    "date":  idx[i].strftime("%d/%m"),
                    "strength": min(strength, 999),
                    "type": "demand",
                    "tested": bool(cur < h[i] * 1.01),  # price is near/in OB
                })
        # Bearish OB: bullish candle followed by strong bearish move (supply zone)
        if len(bears) < max_each and c[i] > o[i]:
            fmin = l[i+1:min(i+6,len(df))].min()
            if fmin < l[i]*0.997 and cur < h[i]:
                strength = round((l[i] - fmin) / max(h[i]-l[i], 0.001) * 100, 1)
                bears.append({
                    "price": round((h[i]+l[i])/2, 2),
                    "high":  round(h[i], 2),
                    "low":   round(l[i], 2),
                    "date":  idx[i].strftime("%d/%m"),
                    "strength": min(strength, 999),
                    "type": "supply",
                    "tested": bool(cur > l[i] * 0.99),  # price is near/in OB
                })
        if len(bulls) >= max_each and len(bears) >= max_each:
            break
    return bulls, bears


# ─── Fibonacci Seviyeleri ─────────────────────────────────────────────────────

def _fibonacci(df, sh, sl):
    """Fibonacci retracement + extension levels from the most recent major swing."""
    if len(sh) < 1 or len(sl) < 1:
        return None
    h, l, c = df['High'].values, df['Low'].values, df['Close'].values
    idx = df.index
    last_sh = sh[-1]
    last_sl = sl[-1]
    swing_h = float(h[last_sh])
    swing_l = float(l[last_sl])
    diff = swing_h - swing_l
    if diff <= 0:
        return None

    # Determine direction: if most recent point is a high → retracing down from high
    if last_sh > last_sl:
        trend = "down"   # swing high is more recent — retracing
        origin, end = swing_h, swing_l
        # Retracement: measured from swing_h downward
        retrace = {
            "0.0":   round(swing_h, 2),
            "0.236": round(swing_h - diff * 0.236, 2),
            "0.382": round(swing_h - diff * 0.382, 2),
            "0.500": round(swing_h - diff * 0.500, 2),
            "0.618": round(swing_h - diff * 0.618, 2),
            "0.786": round(swing_h - diff * 0.786, 2),
            "1.0":   round(swing_l, 2),
        }
        # Extension below swing_l
        ext = {
            "1.272": round(swing_l - diff * 0.272, 2),
            "1.618": round(swing_l - diff * 0.618, 2),
            "2.0":   round(swing_l - diff * 1.0,   2),
        }
    else:
        trend = "up"     # swing low is more recent — bouncing up
        origin, end = swing_l, swing_h
        # Retracement: measured from swing_l upward
        retrace = {
            "0.0":   round(swing_l, 2),
            "0.236": round(swing_l + diff * 0.236, 2),
            "0.382": round(swing_l + diff * 0.382, 2),
            "0.500": round(swing_l + diff * 0.500, 2),
            "0.618": round(swing_l + diff * 0.618, 2),
            "0.786": round(swing_l + diff * 0.786, 2),
            "1.0":   round(swing_h, 2),
        }
        # Extension above swing_h
        ext = {
            "1.272": round(swing_h + diff * 0.272, 2),
            "1.618": round(swing_h + diff * 0.618, 2),
            "2.0":   round(swing_h + diff * 1.0,   2),
        }

    cur = float(c[-1])
    # Find nearest fib level
    all_levels = {**retrace, **ext}
    nearest = min(all_levels.items(), key=lambda x: abs(x[1] - cur))

    return {
        "trend":      trend,
        "swing_high": round(swing_h, 2),
        "swing_low":  round(swing_l, 2),
        "sh_date":    idx[last_sh].strftime("%d/%m"),
        "sl_date":    idx[last_sl].strftime("%d/%m"),
        "retracement": retrace,
        "extension":   ext,
        "nearest_level": nearest[0],
        "nearest_price": nearest[1],
    }


# ─── Fair Value Gap ───────────────────────────────────────────────────────────

def _fvg(df, lb=60):
    h, l, idx = df['High'].values, df['Low'].values, df.index
    bull = bear = None
    for i in range(len(df)-1, max(2,len(df)-lb), -1):
        if bull is None and l[i] > h[i-2]:
            bull = {"price": round((l[i]+h[i-2])/2,2), "high": round(l[i],2),
                    "low": round(h[i-2],2), "date": idx[i-1].strftime("%d/%m %H:%M")}
        if bear is None and h[i] < l[i-2]:
            bear = {"price": round((h[i]+l[i-2])/2,2), "high": round(l[i-2],2),
                    "low": round(h[i],2), "date": idx[i-1].strftime("%d/%m %H:%M")}
        if bull and bear: break
    return bull, bear


# ─── MACD Cross Tespiti ───────────────────────────────────────────────────────

def _macd_cross(hist, macd_line, idx, lb=20):
    for i in range(len(hist)-1, max(1,len(hist)-lb), -1):
        if hist.iloc[i] > 0 and hist.iloc[i-1] <= 0:
            return {"type": "Bullish Cross", "bullish": True,
                    "value": round(float(macd_line.iloc[i]),3),
                    "date": idx[i].strftime("%d/%m %H:%M")}
        if hist.iloc[i] < 0 and hist.iloc[i-1] >= 0:
            return {"type": "Bearish Cross", "bullish": False,
                    "value": round(float(macd_line.iloc[i]),3),
                    "date": idx[i].strftime("%d/%m %H:%M")}
    bul = float(hist.iloc[-1]) > 0
    return {"type": "Bullish" if bul else "Bearish", "bullish": bul,
            "value": round(float(macd_line.iloc[-1]),3),
            "date": idx[-1].strftime("%d/%m %H:%M")}


# ─── Mum Formasyonları ────────────────────────────────────────────────────────

def _candle_patterns(df, lookback=5):
    o,h,l,c = df['Open'].values, df['High'].values, df['Low'].values, df['Close'].values
    idx = df.index
    pats = []
    for i in range(max(1,len(df)-lookback), len(df)):
        body  = abs(c[i]-o[i])
        rng   = h[i]-l[i]
        upper = h[i]-max(c[i],o[i])
        lower = min(c[i],o[i])-l[i]
        if rng < 1e-9: continue
        d = idx[i].strftime("%d/%m")
        # Boğa Yutan
        if c[i-1]<o[i-1] and c[i]>o[i] and o[i]<=c[i-1] and c[i]>=o[i-1]:
            pats.append({"ad":"Boğa Yutan Mum","bull":True,"date":d})
        # Ayı Yutan
        elif c[i-1]>o[i-1] and c[i]<o[i] and o[i]>=c[i-1] and c[i]<=o[i-1]:
            pats.append({"ad":"Ayı Yutan Mum","bull":False,"date":d})
        # Pin Bar / Çekiç
        elif lower>body*2.0 and upper<body*0.6 and lower>rng*0.5:
            pats.append({"ad":"Pin Bar (Çekiç)","bull":True,"date":d})
        # Kayan Yıldız
        elif upper>body*2.0 and lower<body*0.6 and upper>rng*0.5:
            pats.append({"ad":"Kayan Yıldız","bull":False,"date":d})
        # İçeride Kalan Mum
        elif h[i]<h[i-1] and l[i]>l[i-1]:
            pats.append({"ad":"İçeride Kalan Mum","bull":None,"date":d})
    return pats[-3:]


# ─── Hacim Analizi ─────────────────────────────────────────────────────────────

def _volume_analysis(df):
    vol   = df['Volume'].values.astype(float)
    close = df['Close'].values
    avg20 = vol[-20:].mean() if len(vol) >= 20 else vol.mean()
    cur   = float(vol[-1])
    rel   = round(cur/avg20, 2) if avg20 > 0 else 1.0
    up    = float(close[-1]) >= float(close[-2]) if len(close) > 1 else True
    high  = cur > avg20*1.3
    if cur > avg20*3.0:
        return "KLİMAX", "Doyum hacmi (Climax) — tersine dönüş sinyali olabilir ⚠", rel
    elif up and high:
        return "YUKSEK", "Yüksek hacimli yükseliş — güçlü alım baskısı ✓", rel
    elif up and not high:
        return "DUSUK",  "Düşük hacimli yükseliş — zayıf katılım, dikkat", rel
    elif not up and high:
        return "YUKSEK", "Yüksek hacimli düşüş — satış baskısı ⚠", rel
    else:
        return "DUSUK",  "Düşük hacimli geri çekilme — tükenme olabilir", rel


# ─── Likidite Süpürme ────────────────────────────────────────────────────────

def _liq_sweep(df, sh, sl):
    h, l, c = df['High'].values, df['Low'].values, df['Close'].values
    idx = df.index
    for i in range(len(df)-3, max(len(df)-15, 0), -1):
        if sl:
            li = sl[-1]
            if li < i and l[i] < l[li] and c[i] > l[li]:
                return {"type":"Boğa Tuzağı Süpürme","bull":True,
                        "price":round(l[i],2),"date":idx[i].strftime("%d/%m %H:%M")}
        if sh:
            hi = sh[-1]
            if hi < i and h[i] > h[hi] and c[i] < h[hi]:
                return {"type":"Ayı Tuzağı Süpürme","bull":False,
                        "price":round(h[i],2),"date":idx[i].strftime("%d/%m %H:%M")}
    return None


# ─── Spot SL / TP ─────────────────────────────────────────────────────────────

def _spot_sltp(price, atr, bull_ob, bull_fvg, supports):
    if bull_ob:
        sl = round(bull_ob["low"] * 0.988, 2)   # OB altına %1.2 tampon
    elif supports:
        sl = round(supports[0] * 0.985, 2)
    else:
        sl = round(price - atr * 1.5, 2)

    sl    = max(sl, round(price * 0.90, 2))      # max %10 stop
    risk  = max(price - sl, price * 0.02)

    tp1 = round(price + risk * 1.5, 2)
    tp2 = round(price + risk * 3.0, 2)

    if bull_fvg and bull_fvg["high"] > price * 1.005:
        tp1 = round(bull_fvg["high"], 2)

    risk_pct = round((price - sl) / price * 100, 2)
    rr       = round((tp2 - price) / (price - sl), 1)
    return sl, tp1, tp2, risk_pct, rr


# ─── 4H Yeniden Örnekleme ────────────────────────────────────────────────────

def _resample_4h(df_1h):
    if df_1h is None or len(df_1h) < 8:
        return None
    try:
        df = df_1h.resample("4h").agg(
            {"Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"}
        ).dropna()
        return df[df["Volume"] > 0] if len(df) > 10 else None
    except Exception:
        return None


# ─── Tek Zaman Dilimi Analizi ─────────────────────────────────────────────────

def _analyze_tf(df, tf_name: str, tf_type: str = "1d") -> dict | None:
    if df is None or len(df) < 15:
        return None

    c, h, l = df["Close"], df["High"], df["Low"]
    cur = float(c.iloc[-1])

    import math as _math
    _rsi_raw = float(_rsi(c).iloc[-1])
    rsi_val = round(_rsi_raw, 2) if not _math.isnan(_rsi_raw) else None
    ma20    = float(_ema(c,20).iloc[-1])
    ma8     = float(_ema(c,8).iloc[-1])
    ema200  = float(_ema(c,200).iloc[-1]) if len(c) >= 200 else None

    ml, ms_sig, mh = _macd(c)
    macd_cross = _macd_cross(mh, ml, df.index)
    atr_val    = float(_atr(h, l, c).iloc[-1])

    sh, sl  = _swings(df)
    ms, hh, hl, lh, ll = _market_structure(df, sh, sl)

    bull_ob, bear_ob      = _order_blocks(df)
    bull_obs, bear_obs    = _order_blocks_multi(df)
    bull_fvg, bear_fvg    = _fvg(df)
    supports, resists     = _sr_levels(df, sh, sl)
    fib_levels            = _fibonacci(df, sh, sl)

    vol_state, vol_desc, rel_vol = _volume_analysis(df)
    candle_pats = _candle_patterns(df)
    liq_sw      = _liq_sweep(df, sh, sl)

    sl_v, tp1, tp2, risk_pct, rr = _spot_sltp(cur, atr_val, bull_ob, bull_fvg, supports)

    trend     = "BOĞA" if cur > ma8 else "AYI"
    rsi_state = ("AŞIRI ALIM" if rsi_val and rsi_val > 70 else
                 "AŞIRI SATIM" if rsi_val and rsi_val < 30 else "NORMAL")

    bos = None
    if sh and cur > float(h.iloc[sh[-1]]):
        bos = "Yükseliş BOS"
    elif sl and cur < float(l.iloc[sl[-1]]):
        bos = "Düşüş BOS"

    lb = min(200, len(df))
    ph = float(h.iloc[-lb:].max())
    pl = float(l.iloc[-lb:].min())
    zone_pct  = (cur - pl) / (ph - pl) if ph != pl else 0.5
    price_zone = "PAHALI" if zone_pct > 0.5 else "UCUZ"

    # ── TF Skoru — zaman dilimine göre farklı ağırlıklar ─────────────────────
    score = 0.0
    reasons = []
    up_bar = float(c.iloc[-1]) >= float(c.iloc[-2])

    if tf_type in ("1w", "1mo"):
        # ── HAFTALIK / AYLIK: büyük trend + EMA200 dominant ──────────────────

        # Piyasa yapısı (haftalık/aylık trendde en kritik faktör)
        ms_w = 45 if tf_type == "1mo" else 40
        if ms == "YUKSELIS":
            score += ms_w; reasons.append("Uzun vadeli yükseliş yapısı (HH+HL) ✓")
        elif ms == "YATAY":
            score += ms_w * 0.25; reasons.append("Yatay konsolidasyon")
        else:
            score += 0; reasons.append("Uzun vadeli düşüş yapısı (LH+LL) ⚠")

        if bos == "Yükseliş BOS":
            score += 12; reasons.append("Büyük zaman dilimi yapı kırılımı ✓")

        # EMA200 — uzun vadede en önemli dinamik destek/direnç
        ema200_w = 18 if tf_type == "1mo" else 14
        if ema200:
            if cur > ema200 * 1.05:
                score += ema200_w; reasons.append(f"EMA200 belirgin üzerinde (+%{((cur/ema200-1)*100):.1f}) ✓")
            elif cur > ema200:
                score += ema200_w * 0.7; reasons.append("EMA200 üzerinde ✓")
            elif cur > ema200 * 0.95:
                score += ema200_w * 0.2; reasons.append("EMA200 yakınında — kritik bölge")
            else:
                score -= 8; reasons.append("EMA200 altında — uzun vadeli baskı ⚠")

        # RSI — uzun vadede çok geniş bant normal kabul edilir
        rsi_lo = 30 if tf_type == "1mo" else 35
        rsi_hi = 75 if tf_type == "1mo" else 72
        rsi_ob = 82 if tf_type == "1mo" else 78
        if rsi_val is None:
            score += 5  # RSI yok — nötr
        elif rsi_val < rsi_lo:
            score += 14; reasons.append(f"RSI derin aşırı satım — güçlü dönüş fırsatı ({rsi_val}) ✓")
        elif rsi_val < 45:
            score += 10; reasons.append(f"RSI toparlanma bölgesi ({rsi_val})")
        elif rsi_val <= rsi_hi:
            score += 8;  reasons.append(f"RSI sağlıklı momentum bölgesi ({rsi_val}) ✓")
        elif rsi_val <= rsi_ob:
            score += 3;  reasons.append(f"RSI yüksek ama sürdürülebilir ({rsi_val})")
        else:
            score -= 8;  reasons.append(f"RSI aşırı alım — uzun vadeli risk ({rsi_val}) ⚠")

        # Haftalık/aylık MACD — çok güçlü sinyal
        macd_w = 14 if tf_type == "1mo" else 16
        if macd_cross["bullish"]:
            if macd_cross["type"] == "Bullish Cross":
                score += macd_w; reasons.append(f"{'Aylık' if tf_type=='1mo' else 'Haftalık'} MACD Bullish Cross — güçlü sinyal ✓")
            else:
                score += macd_w * 0.5
        else:
            if macd_cross["type"] == "Bearish Cross":
                score -= macd_w * 0.6; reasons.append(f"{'Aylık' if tf_type=='1mo' else 'Haftalık'} MACD Bearish Cross ⚠")

        # OB/FVG — büyük zaman diliminde daha az ağırlık ama hâlâ önemli
        ob_w = 8 if tf_type == "1mo" else 12
        if bull_ob:
            if cur <= bull_ob["high"] * 1.03:
                score += ob_w; reasons.append(f"{'Aylık' if tf_type=='1mo' else 'Haftalık'} Bullish OB bölgesinde ✓")
            else:
                score += ob_w * 0.4; reasons.append("Büyük zaman dilimi OB mevcut")
        if bull_fvg and cur <= bull_fvg["high"] * 1.02:
            score += 5; reasons.append("Kapanmamış FVG ✓")

        # Hacim — uzun vadede yüksek hacim daha anlamlı
        if vol_state == "YUKSEK" and up_bar:
            score += 8; reasons.append("Yüksek hacimli uzun vadeli yükseliş ✓")
        elif vol_state == "KLİMAX":
            score -= 6; reasons.append("Doyum hacmi — tersine dönüş riski ⚠")

        # Mum formasyonları — büyük TF'de çok güçlü sinyal
        for p in candle_pats[:2]:
            if p["bull"] is True:
                score += 6; reasons.append(f"{p['ad']} (büyük TF — güçlü sinyal) ✓")
            elif p["bull"] is False:
                score -= 4; reasons.append(f"{p['ad']} (büyük TF — dikkat) ⚠")

        # Normalize: haftalık/aylık 100 ham → 0-10
        norm = 100 if tf_type == "1mo" else 105

    else:
        # ── GÜNLÜK / 4 SAATLİK: kısa vadeli giriş odaklı ────────────────────

        if ms == "YUKSELIS":
            score += 20; reasons.append("Piyasa yapısı yükseliş (HH+HL) ✓")
        elif ms == "YATAY":
            score += 7; reasons.append("Yatay bant")
        else:
            score += 0;  reasons.append("Düşüş yapısı (LH+LL) ⚠")

        if bos == "Yükseliş BOS":
            score += 8; reasons.append("Yapı kırılımı (BOS) yukarı ✓")

        if bull_ob:
            if cur <= bull_ob["high"] * 1.02:
                score += 14; reasons.append("Fiyat Bullish OB'de — ideal giriş ✓")
            else:
                score += 7; reasons.append("Bullish OB mevcut")
        if bull_fvg:
            if cur <= bull_fvg["high"] * 1.01:
                score += 6;  reasons.append("Bullish FVG kapanmamış ✓")
            else:
                score += 3

        if rsi_val is None:
            score += 5  # RSI yok — nötr
        elif 40 <= rsi_val <= 60:
            score += 8; reasons.append(f"RSI optimal bölge ({rsi_val})")
        elif 30 <= rsi_val < 40:
            score += 6;  reasons.append(f"RSI aşırı satım yakını ({rsi_val})")
        elif rsi_val < 30:
            score += 8;  reasons.append(f"RSI aşırı satım — dönüş fırsatı ({rsi_val}) ✓")
        elif rsi_val > 70:
            score -= 4;  reasons.append(f"RSI aşırı alım ({rsi_val}) ⚠")

        if macd_cross["bullish"]:
            if macd_cross["type"] == "Bullish Cross":
                score += 8; reasons.append("MACD Bullish Cross ✓")
            else:
                score += 4
        else:
            if macd_cross["type"] == "Bearish Cross":
                score -= 4;  reasons.append("MACD Bearish Cross ⚠")

        if ema200 and cur > ema200:
            score += 4; reasons.append("EMA200 üzerinde ✓")
        elif ema200 and cur < ema200:
            score -= 2; reasons.append("EMA200 altında ⚠")

        # EMA8 / EMA20 hizalanması — kısa vadeli trend yönü
        if ma8 > ma20 * 1.001:
            score += 5; reasons.append("EMA8 > EMA20 — kısa vade hizalı ✓")
        elif ma8 < ma20 * 0.999:
            score -= 3; reasons.append("EMA8 < EMA20 — kısa vade negatif ⚠")

        if vol_state == "YUKSEK" and up_bar:
            score += 7; reasons.append("Yüksek hacimli yükseliş ✓")
        elif vol_state == "KLİMAX":
            score -= 4;  reasons.append("Doyum hacmi — tersine dönüş riski ⚠")
        elif vol_state == "DUSUK" and up_bar:
            score += 2

        for p in candle_pats:
            if p["bull"] is True:
                score += 4;  reasons.append(f"{p['ad']} ({p['date']}) ✓")
            elif p["bull"] is False:
                score -= 2;  reasons.append(f"{p['ad']} ({p['date']}) ⚠")

        # ── Momentum bileşeni (en kanıtlı öngörü faktörü) ────────────────────
        # 5 günlük momentum: hisse zaten yükseliyorsa → yükselmeye devam etme eğilimi
        if len(c) >= 6:
            mom_5d = (float(c.iloc[-1]) - float(c.iloc[-6])) / max(float(c.iloc[-6]), 0.001) * 100
            if mom_5d > 5:
                score += 12; reasons.append(f"Güçlü 5G momentum (+{mom_5d:.1f}%) ✓")
            elif mom_5d > 2:
                score += 10; reasons.append(f"Pozitif 5G momentum (+{mom_5d:.1f}%) ✓")
            elif mom_5d > 0:
                score += 5;  reasons.append(f"Hafif yükseliş momentumu (+{mom_5d:.1f}%)")
            elif mom_5d > -2:
                score += 0   # nötr
            elif mom_5d > -5:
                score -= 8;  reasons.append(f"Negatif momentum ({mom_5d:.1f}%) ⚠")
            else:
                score -= 15; reasons.append(f"Güçlü düşüş momentumu ({mom_5d:.1f}%) ⚠")
        else:
            mom_5d = 0

        # 20 günlük momentum: orta vadeli trend onayı
        if len(c) >= 21:
            mom_20d = (float(c.iloc[-1]) - float(c.iloc[-21])) / max(float(c.iloc[-21]), 0.001) * 100
            if mom_20d > 10:
                score += 10; reasons.append(f"Güçlü 20G trend (+{mom_20d:.1f}%) ✓")
            elif mom_20d > 3:
                score += 5;  reasons.append(f"Pozitif 20G trend (+{mom_20d:.1f}%)")
            elif mom_20d < -10:
                score -= 8;  reasons.append(f"Güçlü 20G düşüş ({mom_20d:.1f}%) ⚠")
            elif mom_20d < -3:
                score -= 4

        # Bollinger Bands — fiyat alt banda yakınsa dönüş fırsatı
        if len(c) >= 20:
            bb_mid, bb_up, bb_lo = _bollinger(c)
            bb_range = bb_up - bb_lo if bb_up != bb_lo else 1
            bb_pos = (cur - bb_lo) / bb_range  # 0=alt, 1=üst
            if bb_pos <= 0.15:
                score += 7; reasons.append(f"Fiyat alt Bollinger bandında — dönüş bölgesi ✓")
            elif bb_pos <= 0.35:
                score += 4; reasons.append(f"Alt Bollinger bandına yakın")
            elif bb_pos >= 0.9:
                score -= 4; reasons.append(f"Üst Bollinger bandına yapışık — aşırı alım ⚠")

        norm = 115  # BB + EMA hizalama bileşenleri eklendi

    tf_score = round(max(0, min(10, score / norm * 10)), 1)

    # ── Setup türü: iki yüksek olasılıklı senaryo ─────────────────────────────
    # KIRILIM: Hacimli kırılım + pozitif momentum → momentum yakalaması hedefi
    # DÖNÜŞ  : Aşırı satım + destek seviyesi + toparlanma sinyali
    setup_type = "STANDART"
    if tf_type in ("1d", "4h"):
        _m5 = (float(c.iloc[-1]) - float(c.iloc[-6])) / max(float(c.iloc[-6]), 0.001) * 100 if len(c) >= 6 else 0
        if bos == "Yükseliş BOS" and rel_vol >= 2.0 and _m5 > 3:
            setup_type = "KIRILIM"
        elif rsi_val is not None and rsi_val < 35 and price_zone == "UCUZ" and vol_state != "KLİMAX":
            setup_type = "DÖNÜŞ"

    return {
        "tf": tf_name,
        "market_structure": ms,
        "hh": hh, "hl": hl, "lh": lh, "ll": ll,
        "trend": trend, "price_zone": price_zone,
        "ma20":  round(ma20,2),
        "ma8":   round(ma8,2),
        "ema200": round(ema200,2) if ema200 else None,
        "rsi": rsi_val, "rsi_state": rsi_state,
        "macd": macd_cross,
        "atr": round(atr_val,2),
        "rel_vol": rel_vol,
        "vol_state": vol_state, "vol_desc": vol_desc,
        "supports": [round(v,2) for v in supports],
        "resistances": [round(v,2) for v in resists],
        "bull_ob": bull_ob, "bear_ob": bear_ob,
        "bull_obs": bull_obs, "bear_obs": bear_obs,
        "bull_fvg": bull_fvg, "bear_fvg": bear_fvg,
        "bos": bos, "liq_sweep": liq_sw,
        "fibonacci": fib_levels,
        "candle_patterns": candle_pats,
        "sl": sl_v, "tp1": tp1, "tp2": tp2,
        "risk_pct": risk_pct, "rr": rr,
        "score": tf_score, "reasons": reasons[:8],
        "setup_type": setup_type,
    }


# ─── İstatistiksel Analiz ────────────────────────────────────────────────────

def _stats(df_1d, df_1h):
    day_names = {0:"Pazartesi",1:"Salı",2:"Çarşamba",3:"Perşembe",4:"Cuma"}
    best_days, best_hours = [], []

    if df_1d is not None and len(df_1d) > 20:
        d = df_1d.copy()
        d["ret"] = d["Close"].pct_change()
        d["dow"] = d.index.dayofweek
        da = d.groupby("dow")["ret"].mean()
        top = da[da > 0].nlargest(2).index.tolist()
        best_days = [day_names[i] for i in sorted(top) if i in day_names]

    if df_1h is not None and len(df_1h) > 40:
        h = df_1h.copy()
        h["ret"]  = h["Close"].pct_change()
        h["hour"] = h.index.hour
        h = h[(h["hour"] >= 10) & (h["hour"] <= 17)]
        ha = h.groupby("hour")["ret"].mean()
        top_h = ha[ha > 0].nlargest(4).index.tolist()
        best_hours = [f"{i:02d}:00" for i in sorted(top_h)]

    if not best_days:  best_days  = ["Salı","Perşembe"]
    if not best_hours: best_hours = ["10:00","11:00"]

    avg_range = 0.0
    if df_1d is not None and len(df_1d) > 10:
        ranges = ((df_1d["High"]-df_1d["Low"])/df_1d["Close"]*100).iloc[-20:]
        avg_range = round(float(ranges.mean()), 2)

    return {"best_days": best_days, "best_hours": best_hours,
            "avg_daily_range_pct": avg_range}


# ─── Temel Analiz ─────────────────────────────────────────────────────────────

def _fundamentals(t_obj) -> dict:
    try:
        info = t_obj.info or {}
    except Exception:
        return {}

    def _v(key, pct=False, mult=None):
        val = info.get(key)
        if val is None or val != val:  # None or NaN
            return None
        if mult:
            val = val * mult
        return round(float(val) * 100, 2) if pct else round(float(val), 2)

    def _fmt_cap(val):
        if val is None:
            return None
        if val >= 1e12:
            return f"{val/1e12:.2f}T ₺"
        if val >= 1e9:
            return f"{val/1e9:.2f}Mrd ₺"
        if val >= 1e6:
            return f"{val/1e6:.2f}Mn ₺"
        return f"{val:,.0f} ₺"

    mc_raw = info.get("marketCap")
    return {
        "fk":              _v("trailingPE"),            # F/K (P/E)
        "fk_forward":      _v("forwardPE"),             # İleride F/K
        "pd_dd":           _v("priceToBook"),           # PD/DD (P/B)
        "piyasa_degeri":   _fmt_cap(mc_raw),            # Piyasa Değeri
        "eps":             _v("trailingEps"),           # Hisse Başı Kâr
        "temttu_verimi":   _v("dividendYield"),            # Temettü Verimi % (yfinance zaten % olarak verir)
        "roe":             _v("returnOnEquity", pct=True), # Özkaynak Karlılığı %
        "roa":             _v("returnOnAssets", pct=True), # Aktif Karlılığı %
        "borc_ozkaynak":   _v("debtToEquity"),          # Borç/Özkaynak
        "gelir_buyume":    _v("revenueGrowth", pct=True),  # Gelir Büyümesi %
        "kar_buyume":      _v("earningsGrowth", pct=True), # Kâr Büyümesi %
        "brut_kar_marji":  _v("grossMargins", pct=True),   # Brüt Kar Marjı %
        "net_kar_marji":   _v("profitMargins", pct=True),  # Net Kar Marjı %
        "cari_oran":       _v("currentRatio"),          # Cari Oran
        "hizli_oran":      _v("quickRatio"),            # Hızlı Oran
        "faaliyet_marji":  _v("operatingMargins", pct=True),  # Faaliyet Marjı %
        "ev_favok":           _v("enterpriseToEbitda"),    # EV/FAVÖK
        "ebitda":             _v("ebitda"),                # FAVÖK (₺)
        "net_gelir":          _v("netIncomeToCommon"),     # Net Kâr (₺)
        "ozkaynak":           _v("bookValue"),             # Defter Değeri / hisse (₺)
        "hisse_sayisi":       info.get("sharesOutstanding"), # Hisse Adedi
        "toplam_gelir":       _v("totalRevenue"),          # Toplam Gelir (₺)
        "serbest_nakit_akisi":_v("freeCashflow"),          # Serbest Nakit Akışı
        "sektor":             info.get("sector"),
        "endustri":           info.get("industry"),
    }


# ─── Temel Analiz Skoru ───────────────────────────────────────────────────────

def _fundamental_score(f: dict) -> tuple[float, str]:
    """Temel verilere göre 0–10 skor + yorum döndürür."""
    if not f:
        return None, None

    score = 0.0
    reasons = []
    weight = 0.0   # kaç metrik hesaba katıldı

    # F/K (P/E) — düşük iyi
    fk = f.get("fk")
    if fk is not None:
        weight += 2
        if 0 < fk <= 10:
            score += 2.0; reasons.append(f"F/K çok düşük ({fk}) — ucuz ✓")
        elif 0 < fk <= 20:
            score += 1.5; reasons.append(f"F/K makul ({fk}) ✓")
        elif 0 < fk <= 30:
            score += 0.8; reasons.append(f"F/K orta ({fk})")
        elif fk > 30:
            score += 0.0; reasons.append(f"F/K yüksek ({fk}) ⚠")
        else:  # negatif → zarar eden şirket
            score -= 0.5; reasons.append(f"Negatif F/K — zarar ⚠")

    # PD/DD (P/B) — düşük iyi
    pd_dd = f.get("pd_dd")
    if pd_dd is not None:
        weight += 1.5
        if pd_dd < 1:
            score += 1.5; reasons.append(f"PD/DD defter değerinin altında ({pd_dd}) ✓")
        elif pd_dd <= 2:
            score += 1.0; reasons.append(f"PD/DD makul ({pd_dd}) ✓")
        elif pd_dd <= 5:
            score += 0.3
        else:
            score -= 0.3; reasons.append(f"PD/DD yüksek ({pd_dd}) ⚠")

    # ROE — yüksek iyi
    roe = f.get("roe")
    if roe is not None:
        weight += 2
        if roe >= 25:
            score += 2.0; reasons.append(f"ROE yüksek (%{roe}) ✓")
        elif roe >= 15:
            score += 1.5; reasons.append(f"ROE iyi (%{roe}) ✓")
        elif roe >= 5:
            score += 0.8
        else:
            score -= 0.5; reasons.append(f"ROE düşük (%{roe}) ⚠")

    # Net Kar Marjı
    npm = f.get("net_kar_marji")
    if npm is not None:
        weight += 1.5
        if npm >= 20:
            score += 1.5; reasons.append(f"Net kar marjı yüksek (%{npm}) ✓")
        elif npm >= 10:
            score += 1.0; reasons.append(f"Net kar marjı iyi (%{npm}) ✓")
        elif npm >= 0:
            score += 0.4
        else:
            score -= 0.5; reasons.append(f"Net kar marjı negatif (%{npm}) ⚠")

    # Gelir Büyümesi
    gb = f.get("gelir_buyume")
    if gb is not None:
        weight += 1.5
        if gb >= 20:
            score += 1.5; reasons.append(f"Gelir büyümesi güçlü (%{gb}) ✓")
        elif gb >= 10:
            score += 1.0
        elif gb >= 0:
            score += 0.4
        else:
            score -= 0.5; reasons.append(f"Gelir düşüyor (%{gb}) ⚠")

    # Borç/Özkaynak
    boe = f.get("borc_ozkaynak")
    if boe is not None:
        weight += 1
        if boe < 30:
            score += 1.0; reasons.append(f"Düşük borç/özkaynak ({boe}) ✓")
        elif boe <= 70:
            score += 0.5
        elif boe > 150:
            score -= 0.5; reasons.append(f"Yüksek borçluluk ({boe}) ⚠")

    # Temettü verimi
    tv = f.get("temttu_verimi")
    if tv is not None and tv > 0:
        weight += 0.5
        if tv >= 5:
            score += 0.5; reasons.append(f"Temettü verimi yüksek (%{tv}) ✓")
        elif tv >= 2:
            score += 0.3

    # Cari oran
    co = f.get("cari_oran")
    if co is not None:
        weight += 0.5
        if co >= 2:
            score += 0.5; reasons.append(f"Güçlü cari oran ({co}) ✓")
        elif co >= 1.5:
            score += 0.3
        elif co < 1:
            score -= 0.3; reasons.append(f"Cari oran 1'in altında ({co}) ⚠")

    if weight == 0:
        return None, None

    # Normalize 0–10
    max_possible = weight  # her kategori max kendi ağırlığını alabilir
    norm = round(max(0, min(10, (score / max_possible) * 10)), 1)

    # Genel yorum
    if norm >= 7:
        verdict = "Temel görünüm güçlü"
    elif norm >= 5:
        verdict = "Temel görünüm orta"
    elif norm >= 3:
        verdict = "Temel görünüm zayıf"
    else:
        verdict = "Temel görünüm olumsuz"

    return norm, verdict, reasons[:4]


# ─── Haber & Duygu Analizi ────────────────────────────────────────────────────

_POS_KW = {
    # English
    'surge','gain','rise','rally','growth','profit','record','beat','strong',
    'positive','upgrade','outperform','exceed','deal','partnership','expand',
    'revenue','dividend','boosts','wins','higher','bullish','recover','rebound',
    'buy','overweight','target raised','outlook raised','breakout','acquisition',
    # Turkish
    'artış','yükseliş','rekor','büyüme','güçlü','olumlu','tavan','anlaşma',
    'büyüdü','arttı','kazanç','ihracat','başarı','yüksek','kâr','kar açıkladı',
    'temettü','hedef yükseltildi','alım','pozitif','yukarı revize',
}
_NEG_KW = {
    # English
    'fall','drop','decline','loss','risk','concern','crisis','weak','sell',
    'downgrade','miss','below','pressure','warning','default','debt','lawsuit',
    'tumble','plunge','cut','bearish','investigation','fraud','writedown',
    'target lowered','outlook cut','shutdown','layoff','fine','penalty',
    # Turkish
    'düşüş','kayıp','zarar','endişe','kriz','düştü','azaldı','zayıf','satış',
    'taban','iflas','baskı','soruşturma','düşük','olumsuz','aşağı revize',
    'ceza','dava','zarar açıkladı','hedef düşürüldü','uyarı',
}

def _news_sentiment(t_obj) -> dict:
    """Fetch last 7-day Yahoo Finance news and score sentiment 1-10."""
    import time as _time
    try:
        news_items = t_obj.news or []
    except Exception:
        news_items = []

    from datetime import timezone as _tz
    import datetime as _dt

    recent = []
    for item in news_items:
        # New yfinance format: item = {'id': ..., 'content': {...}}
        content = item.get('content', item)
        title = content.get('title', item.get('title', ''))
        if not title:
            continue
        pub_str = content.get('pubDate', content.get('displayTime', ''))
        publisher = ''
        prov = content.get('provider', {})
        if isinstance(prov, dict):
            publisher = prov.get('displayName', '')
        url = ''
        cu = content.get('canonicalUrl', content.get('clickThroughUrl', {}))
        if isinstance(cu, dict):
            url = cu.get('url', '')

        # Parse pubDate ISO string → timestamp
        ts = 0
        if pub_str:
            try:
                ts = _dt.datetime.fromisoformat(pub_str.replace('Z', '+00:00')).timestamp()
            except Exception:
                ts = item.get('providerPublishTime', 0) or 0
        else:
            ts = item.get('providerPublishTime', 0) or 0

        # Accept all articles (yfinance feed is small, ~10 items, often weeks old)
        recent.append({
            'title':     title,
            'publisher': publisher,
            'url':       url,
            'ts':        ts,
        })

    if not recent:
        return {}

    pos_total = neg_total = 0
    scored = []
    for n in recent:
        tl = n['title'].lower()
        pos = sum(1 for kw in _POS_KW if kw in tl)
        neg = sum(1 for kw in _NEG_KW if kw in tl)
        pos_total += pos
        neg_total += neg
        scored.append({**n, 'net': pos - neg})

    total_signals = pos_total + neg_total
    pos_ratio = pos_total / max(total_signals, 1)

    # Score 1-10: pure neutral (no keywords) → 5, full positive → 10, full negative → 1
    if total_signals == 0:
        sentiment_score = 5.0
    else:
        sentiment_score = round(1 + pos_ratio * 9, 1)

    # Label
    if   sentiment_score >= 7.5: label, emoji = 'OLUMLU',   '😊'
    elif sentiment_score >= 6.0: label, emoji = 'HAFIF OLUMLU', '🙂'
    elif sentiment_score >= 4.5: label, emoji = 'NÖTR',     '😐'
    elif sentiment_score >= 3.0: label, emoji = 'KARIŞIK',  '😟'
    else:                        label, emoji = 'OLUMSUZ',  '😨'

    # Top 3 drivers: headlines with highest |net| score
    top3 = sorted(scored, key=lambda x: abs(x['net']), reverse=True)[:3]
    top_drivers = [{
        'title':     d['title'][:130],
        'publisher': d['publisher'],
        'direction': 'pos' if d['net'] > 0 else ('neg' if d['net'] < 0 else 'neu'),
    } for d in top3]

    # Most recent 8 headlines
    display = sorted(recent, key=lambda x: x['ts'], reverse=True)[:8]
    headlines = [{
        'title':     n['title'][:130],
        'publisher': n['publisher'],
        'date':      _time.strftime('%d.%m', _time.localtime(n['ts'])),
    } for n in display]

    # Date range of articles
    all_ts = [n['ts'] for n in recent if n['ts'] > 0]
    oldest = _time.strftime('%d.%m.%Y', _time.localtime(min(all_ts))) if all_ts else ''
    newest = _time.strftime('%d.%m.%Y', _time.localtime(max(all_ts))) if all_ts else ''

    return {
        'sentiment_score': sentiment_score,
        'label':           label,
        'emoji':           emoji,
        'article_count':   len(recent),
        'pos_signals':     pos_total,
        'neg_signals':     neg_total,
        'top_drivers':     top_drivers,
        'headlines':       headlines,
        'date_range':      f"{oldest} – {newest}" if oldest else '',
    }


# ─── Insider Tracker ──────────────────────────────────────────────────────────

def _insider_tracker(t_obj) -> dict:
    """
    Insider & kurumsal sahiplik takibi.
    - insider_transactions (SEC Form 4 benzeri, US listelemeli hisseler için)
    - institutional_holders + major_holders (BIST .IS hisseleri için proxy)
    Dönemler: son 1 gün, 7 gün, 30 gün, 180 gün.
    """
    import time as _time
    import pandas as pd
    import numpy as np

    now = _time.time()
    cutoffs = {'1g': now-86400, '7g': now-7*86400, '30g': now-30*86400, '6ay': now-180*86400}

    # ── 1. Gerçek insider_transactions (US hisseler, SEC Form 4) ─────────────
    transactions = []
    try:
        ins_tx = t_obj.insider_transactions
        if ins_tx is not None and not ins_tx.empty:
            for _, row in ins_tx.iterrows():
                try:
                    dt = row.get('Start Date', row.get('Date'))
                    if dt is None: continue
                    ts = dt.timestamp() if hasattr(dt,'timestamp') else pd.Timestamp(dt).timestamp()
                    shares   = float(row.get('Shares', 0) or 0)
                    value    = float(row.get('Value', 0) or 0)
                    tx_type  = str(row.get('Transaction', '')).strip()
                    name     = str(row.get('Insider', 'Bilinmiyor')).strip()
                    title    = str(row.get('Position', '')).strip()
                    is_buy   = any(w in tx_type.lower() for w in ['buy','purchase','acquisition'])
                    is_sell  = any(w in tx_type.lower() for w in ['sell','sale'])
                    is_exec  = any(w in title.lower() for w in
                                   ['ceo','cfo','coo','president','chairman','director','officer'])
                    value_abs = abs(value)
                    informative = (is_sell and is_exec and value_abs > 200_000
                                   and 'option' not in tx_type.lower()
                                   and 'plan' not in tx_type.lower())
                    transactions.append({
                        'ts': ts, 'name': name[:40], 'title': title[:40],
                        'tx_type': tx_type, 'is_buy': is_buy, 'is_sell': is_sell,
                        'informative': informative, 'shares': int(abs(shares)),
                        'value': round(value_abs),
                    })
                except Exception:
                    continue
    except Exception:
        pass

    # ── 2. Institutional holders (BIST proxy) ─────────────────────────────────
    inst_holders = []
    major = {}
    try:
        ih = t_obj.institutional_holders
        if ih is not None and not ih.empty:
            for _, row in ih.iterrows():
                try:
                    pct_chg = float(row.get('pctChange', 0) or 0)
                    holder  = str(row.get('Holder', '')).strip()
                    shares  = float(row.get('Shares', 0) or 0)
                    pct_held = float(row.get('pctHeld', 0) or 0)
                    # pctChange > 0 → bought more; < 0 → reduced
                    inst_holders.append({
                        'holder':   holder[:50],
                        'pct_chg':  round(pct_chg * 100, 2),
                        'pct_held': round(pct_held * 100, 2),
                        'shares':   int(shares),
                        'action':   'ALIM' if pct_chg > 0.01 else ('SATIM' if pct_chg < -0.01 else 'SABİT'),
                    })
                except Exception:
                    continue
    except Exception:
        pass

    try:
        mh = t_obj.major_holders
        if mh is not None and not mh.empty:
            for _, row in mh.iterrows():
                key = str(row.get('Breakdown', '')).strip()
                val = row.get('Value', 0)
                try:
                    major[key] = round(float(val) * 100, 2)
                except Exception:
                    pass
    except Exception:
        pass

    has_transactions = len(transactions) > 0
    has_inst = len(inst_holders) > 0

    if not has_transactions and not has_inst:
        return {}

    # ── Period summaries from actual insider transactions ─────────────────────
    periods = {}
    if has_transactions:
        for label, cutoff in cutoffs.items():
            subset = [t for t in transactions if t['ts'] >= cutoff]
            if not subset: continue
            buys  = [t for t in subset if t['is_buy']]
            sells = [t for t in subset if t['is_sell']]
            info_sells = [t for t in subset if t['informative']]
            buy_val  = sum(t['value'] for t in buys)
            sell_val = sum(t['value'] for t in sells)
            net      = buy_val - sell_val
            if net > 0:     sig, col = 'ALIM AĞIRLIKLI', 'bull'
            elif info_sells: sig, col = 'BİLGİSEL SATIM ⚠', 'warn'
            elif net < 0:   sig, col = 'RUTİN SATIM', 'bear'
            else:            sig, col = 'DENGELİ', 'neu'
            periods[label] = {
                'buy_count': len(buys), 'sell_count': len(sells),
                'net_flow': net, 'signal': sig, 'color': col,
                'info_sell_cnt': len(info_sells),
                'transactions': [{
                    'name': t['name'], 'title': t['title'], 'tx_type': t['tx_type'],
                    'is_buy': t['is_buy'], 'informative': t['informative'],
                    'shares': t['shares'], 'value': t['value'],
                    'date': _time.strftime('%d.%m.%Y', _time.localtime(t['ts'])),
                } for t in sorted(subset, key=lambda x:x['ts'], reverse=True)[:5]],
            }

    # ── Overall signal ────────────────────────────────────────────────────────
    if has_transactions and periods:
        ref = periods.get('6ay', periods.get('30g', next(iter(periods.values()))))
        overall_signal, overall_color = ref['signal'], ref['color']
    elif has_inst:
        # Derive signal from institutional pct_chg
        net_inst = sum(h['pct_chg'] for h in inst_holders)
        buyers   = [h for h in inst_holders if h['action'] == 'ALIM']
        sellers  = [h for h in inst_holders if h['action'] == 'SATIM']
        if net_inst > 1:    overall_signal, overall_color = 'KURUMSAL ALIM', 'bull'
        elif net_inst < -1: overall_signal, overall_color = 'KURUMSAL SATIM', 'bear'
        else:               overall_signal, overall_color = 'KURUMSAL DENGELİ', 'neu'
    else:
        overall_signal, overall_color = 'VERİ YOK', 'neu'

    return {
        'overall_signal':  overall_signal,
        'overall_color':   overall_color,
        'periods':         periods,
        'total_tx':        len(transactions),
        'inst_holders':    sorted(inst_holders, key=lambda x: abs(x['pct_chg']), reverse=True)[:8],
        'major':           major,
        'data_type':       'form4' if has_transactions else 'institutional',
    }


# ─── Balina & Akıllı Para Sinyalleri ─────────────────────────────────────────

def _whale_signals(df_1d: pd.DataFrame, df_1h=None) -> dict:
    """
    OBV, CMF, MFI, A/D, hacim patlaması ve blok işlem tespiti.
    Gerçek MKK takas verisi yerine proxy: kurumsal birikim/dağıtım paternleri.
    """
    if df_1d is None or len(df_1d) < 20:
        return {}

    c = df_1d['Close'].astype(float)
    h = df_1d['High'].astype(float)
    l = df_1d['Low'].astype(float)
    o = df_1d['Open'].astype(float)
    v = df_1d['Volume'].astype(float)
    idx = df_1d.index

    # ── OBV (On Balance Volume) ──────────────────────────────────────────────
    direction = np.sign(c.diff().fillna(0))
    obv = (direction * v).cumsum()
    obv_ema = obv.ewm(span=10, adjust=False).mean()
    obv_trend = "YUKSELIS" if float(obv.iloc[-1]) > float(obv_ema.iloc[-1]) else "DUSUS"
    # OBV divergence: fiyat yükseliyor ama OBV düşüyorsa — ayı divergansı
    price_up5   = float(c.iloc[-1]) > float(c.iloc[-6])  if len(c) > 5 else False
    obv_up5     = float(obv.iloc[-1]) > float(obv.iloc[-6]) if len(obv) > 5 else False
    obv_div = None
    if price_up5 and not obv_up5:
        obv_div = "Ayı Divergansı ⚠ (Fiyat ↑ OBV ↓)"
    elif not price_up5 and obv_up5:
        obv_div = "Boğa Divergansı ✓ (Fiyat ↓ OBV ↑)"

    # ── CMF (Chaikin Money Flow, 20-periyot) ─────────────────────────────────
    mfv = ((c - l) - (h - c)) / (h - l + 1e-9) * v
    cmf_raw = mfv.rolling(20).sum() / v.rolling(20).sum().replace(0, np.nan)
    cmf = round(float(cmf_raw.iloc[-1]), 3) if not np.isnan(float(cmf_raw.iloc[-1])) else 0.0
    cmf_state = "BIRIKIM" if cmf > 0.05 else ("DAGITIM" if cmf < -0.05 else "NOTR")

    # ── MFI (Money Flow Index, 14-periyot) ───────────────────────────────────
    tp = (h + l + c) / 3
    raw_mf = tp * v
    pos_mf = raw_mf.where(tp > tp.shift(1), 0.0).rolling(14).sum()
    neg_mf = raw_mf.where(tp <= tp.shift(1), 0.0).rolling(14).sum()
    mfi_raw = 100 - 100 / (1 + pos_mf / neg_mf.replace(0, np.nan))
    mfi = round(float(mfi_raw.iloc[-1]), 1) if not np.isnan(float(mfi_raw.iloc[-1])) else 50.0
    mfi_state = "AŞIRI ALIM" if mfi > 80 else ("AŞIRI SATIM" if mfi < 20 else
                "YÜKSELİŞ"  if mfi > 55 else ("DÜŞÜŞ" if mfi < 45 else "NOTR"))

    # ── A/D Çizgisi (Accumulation/Distribution) ──────────────────────────────
    clv = ((c - l) - (h - c)) / (h - l + 1e-9)
    ad = (clv * v).cumsum()
    ad_ema = ad.ewm(span=10, adjust=False).mean()
    ad_trend = "BIRIKIM" if float(ad.iloc[-1]) > float(ad_ema.iloc[-1]) else "DAGITIM"

    # ── Hacim Patlamaları (son 30 gün) ───────────────────────────────────────
    avg20 = float(v.rolling(20).mean().iloc[-1])
    recent = df_1d.tail(30)
    vol_spikes = []
    for i in range(len(recent)):
        vi = float(recent['Volume'].iloc[i])
        if avg20 > 0 and vi > avg20 * 2.0:
            mult = round(vi / avg20, 1)
            ci   = float(recent['Close'].iloc[i])
            oi   = float(recent['Open'].iloc[i])
            chg_pct = round((ci - oi) / oi * 100, 2) if oi > 0 else 0
            vol_spikes.append({
                "date":      recent.index[i].strftime("%d.%m"),
                "multiple":  mult,
                "price_chg": chg_pct,
                "direction": "UP" if chg_pct >= 0 else "DOWN",
            })

    # ── Blok İşlem Tespiti (hacim ≥3x + büyük mum gövdesi) ──────────────────
    body = (c - o).abs()
    avg_body = body.rolling(20).mean()
    block_signals = []
    for s in vol_spikes:
        if s["multiple"] >= 3.0 and abs(s["price_chg"]) > 1.0:
            block_signals.append(s)

    # ── Kurumsal Birikim Proxy (Takas Proxy) ─────────────────────────────────
    # Büyük gövdeli + yüksek hacimli yükseliş günleri → kurumsal alım iz
    last20 = df_1d.tail(20)
    kur_akim = 0  # pozitif = kurumsal alım, negatif = dağıtım
    for i in range(len(last20)):
        vi   = float(last20['Volume'].iloc[i])
        ci   = float(last20['Close'].iloc[i])
        oi   = float(last20['Open'].iloc[i])
        gvde = ci - oi
        if avg20 > 0:
            vol_w = vi / avg20  # hacim ağırlığı
            kur_akim += gvde * vol_w

    # Normalize
    price_ref = float(c.iloc[-1]) or 1.0
    kur_norm  = round(kur_akim / (price_ref * 20), 3)
    takas_signal = "KURUMSAL ALIM" if kur_norm > 0.05 else (
                   "KURUMSAL SATIM" if kur_norm < -0.05 else "DENGELİ")

    # ── Gap (Boşluk) Analizi — genellikle kurumsal/gece emri ─────────────────
    gaps = []
    for i in range(1, min(30, len(df_1d))):
        prev_c = float(df_1d['Close'].iloc[-i-1])
        cur_o  = float(df_1d['Open'].iloc[-i])
        if prev_c > 0:
            gap_pct = round((cur_o - prev_c) / prev_c * 100, 2)
            if abs(gap_pct) >= 1.5:
                gaps.append({
                    "date": df_1d.index[-i].strftime("%d.%m"),
                    "gap_pct": gap_pct,
                    "type": "Yükseliş Boşluğu ✓" if gap_pct > 0 else "Düşüş Boşluğu ⚠",
                })
    gaps = gaps[:4]

    # ── Kompozit Balina Skoru (0–10) ─────────────────────────────────────────
    score = 5.0  # başlangıç nötr
    if cmf > 0.1:         score += 1.5
    elif cmf > 0.03:      score += 0.7
    elif cmf < -0.1:      score -= 1.5
    elif cmf < -0.03:     score -= 0.7
    if obv_trend == "YUKSELIS":   score += 1.0
    elif obv_trend == "DUSUS":    score -= 1.0
    if ad_trend == "BIRIKIM":     score += 0.8
    elif ad_trend == "DAGITIM":   score -= 0.8
    if mfi > 60:                  score += 0.7
    elif mfi < 40:                score -= 0.7
    if kur_norm > 0.1:            score += 1.0
    elif kur_norm < -0.1:         score -= 1.0
    if obv_div == "Ayı Divergansı ⚠ (Fiyat ↑ OBV ↓)":   score -= 0.5
    elif obv_div and "Boğa" in obv_div:                    score += 0.5

    whale_score = round(min(10, max(0, score)), 1)
    smart_money = "ALIYOR 🐋" if whale_score >= 6.5 else (
                  "SATIYOR 🔴" if whale_score <= 3.5 else "NOTR ⚖")

    return {
        "obv_trend":     obv_trend,
        "obv_div":       obv_div,
        "cmf":           cmf,
        "cmf_state":     cmf_state,
        "mfi":           mfi,
        "mfi_state":     mfi_state,
        "ad_trend":      ad_trend,
        "vol_spikes":    vol_spikes[-5:],
        "block_signals": block_signals[-3:],
        "takas_signal":  takas_signal,
        "takas_score":   round(kur_norm, 3),
        "gaps":          gaps,
        "whale_score":   whale_score,
        "smart_money":   smart_money,
    }


# ─── Ana Fonksiyon ────────────────────────────────────────────────────────────

def analyze_stock(ticker: str) -> dict | None:
    yf_t = ticker + ".IS"
    try:
        t_obj = yf.Ticker(yf_t)
        df_1d = _yf_history(t_obj, period="6mo",  interval="1d",  auto_adjust=True)
        df_1h = _yf_history(t_obj, period="60d",  interval="1h",  auto_adjust=True)
        df_1w = _yf_history(t_obj, period="2y",   interval="1wk", auto_adjust=True)

        if df_1d is None or len(df_1d) < 20:
            return {"ticker": ticker, "error": "Yetersiz veri"}

        df_1mo = _yf_history(t_obj, period="10y", interval="1mo", auto_adjust=True)

        for df in [df_1d, df_1h, df_1w]:
            if df is not None:
                for col in ["Dividends","Stock Splits"]:
                    if col in df.columns:
                        df.drop(columns=[col], inplace=True)

        df_4h        = _resample_4h(df_1h if len(df_1h) > 0 else None)
        fundamentals = _fundamentals(t_obj)
        fund_result  = _fundamental_score(fundamentals)
        fund_score   = fund_result[0] if fund_result[0] is not None else None
        fund_verdict = fund_result[1] if len(fund_result) > 1 else None
        fund_reasons = fund_result[2] if len(fund_result) > 2 else []

        cur  = float(df_1d["Close"].iloc[-1])
        prev = float(df_1d["Close"].iloc[-2]) if len(df_1d) > 1 else cur
        chg  = round((cur-prev)/prev*100, 2)
        last_date = df_1d.index[-1].strftime("%d/%m %H:%M")

        tf_4h  = _analyze_tf(df_4h, "4 Saatlik", tf_type="4h")
        tf_1d  = _analyze_tf(df_1d, "Günlük",    tf_type="1d")
        tf_1w  = _analyze_tf(df_1w  if (df_1w  is not None and len(df_1w)  >= 15) else None, "Haftalık", tf_type="1w")
        tf_1mo = _analyze_tf(df_1mo if (df_1mo is not None and len(df_1mo) >= 15) else None, "Aylık",    tf_type="1mo")

        if tf_1d is None:
            return {"ticker": ticker, "error": "Analiz başarısız"}

        stats   = _stats(df_1d, df_1h if (df_1h is not None and len(df_1h) > 20) else None)
        whale   = _whale_signals(df_1d, df_1h)
        from news_sentiment import fetch_news_for_ticker
        news    = fetch_news_for_ticker(ticker, t_obj)
        insider = _insider_tracker(t_obj)

        def _tf_action(score):
            if score >= 7.5: return "GÜÇLÜ AL"
            if score >= 6.0: return "AL"
            if score >= 4.5: return "İZLE"
            if score >= 3.0: return "ZAYIF"
            return "SAT"

        # ── Genel AI Skoru (ağırlıklı: 4h+1d+1w) ──
        parts = []
        if tf_4h: parts.append((tf_4h["score"], 0.25))
        parts.append((tf_1d["score"], 0.50))
        if tf_1w: parts.append((tf_1w["score"], 0.25))
        total_w  = sum(w for _,w in parts)
        ai_score = round(sum(s*w for s,w in parts)/total_w, 1)

        # MTF uyum bonusu/cezası
        tfs = [v for v in [tf_4h, tf_1d, tf_1w] if v]
        if len(tfs) >= 2:
            bull_n = sum(1 for tf in tfs if tf["trend"] == "BOĞA")
            if bull_n == len(tfs):
                ai_score = round(min(10, ai_score + 0.5), 1)
            elif bull_n == 0:
                ai_score = round(max(0, ai_score - 0.5), 1)

        action = _tf_action(ai_score)

        # ── Per-timeframe aksiyonlar ──
        action_4h  = _tf_action(tf_4h["score"])  if tf_4h  else None
        action_1d  = _tf_action(tf_1d["score"])  if tf_1d  else None
        action_1w  = _tf_action(tf_1w["score"])  if tf_1w  else None
        action_1mo = _tf_action(tf_1mo["score"]) if tf_1mo else None

        # Haftalık bias
        weekly_bias = "Nötr"
        if tf_1w:
            if tf_1w["trend"] == "BOĞA": weekly_bias = "Yükseliş"
            elif tf_1w["trend"] == "AYI": weekly_bias = "Düşüş"

        # Long/Short %
        bull_f = sum([
            tf_1d["rsi"] > 50,
            (tf_1d["macd"]["bullish"] if tf_1d["macd"] else False),
            tf_1d["trend"] == "BOĞA",
            weekly_bias == "Yükseliş",
            tf_1d["market_structure"] == "YUKSELIS",
        ])
        long_pct  = min(95, max(5, 50 + bull_f * 8))
        short_pct = 100 - long_pct

        # Market gücü
        mkt_str = 0
        if tf_1d["ema200"] and cur > tf_1d["ema200"]: mkt_str += 30
        if cur > tf_1d["ma8"]:   mkt_str += 30
        if cur > tf_1d["ma20"]:  mkt_str += 25
        if tf_1d["rel_vol"] > 1: mkt_str += 15

        # Özet bullet'lar
        bullets = []
        if tf_1d["market_structure"] == "YUKSELIS":
            bullets.append("Piyasa yapısı yükseliş (HH+HL) ✓")
        elif tf_1d["market_structure"] == "DUSUS":
            bullets.append("Düşüş yapısı — trendle ters işlem riskli ⚠")
        if tf_1d["bull_ob"] and cur <= tf_1d["bull_ob"]["high"] * 1.02:
            bullets.append("Fiyat Bullish OB'de — ideal giriş bölgesi ✓")
        elif tf_1d["price_zone"] == "PAHALI":
            bullets.append("Premium bölge — OB'ye dönüş beklenebilir")
        if tf_1d["rel_vol"] > 1.5:
            bullets.append("Yüksek hacim onayı ✓")
        elif tf_1d["rel_vol"] < 0.7:
            bullets.append("Düşük hacim — katılım zayıf")
        if weekly_bias == "Yükseliş":
            bullets.append("Haftalık yükseliş trendi ✓")
        if tf_1d["rsi"] > 70:
            bullets.append("RSI aşırı alım — dikkat ⚠")

        return {
            "ticker": ticker,
            "price": round(cur,2),
            "change_pct": chg,
            "price_label": tf_1d["price_zone"],
            "last_bar_date": last_date,
            "weekly_bias": weekly_bias,
            "long_pct": long_pct,
            "short_pct": short_pct,
            "market_strength": min(100, mkt_str),
            "ai_confidence": min(100, int(ai_score*10)),
            "rsi": tf_1d["rsi"],
            "rel_vol": tf_1d["rel_vol"],
            "trend": tf_1d["trend"],
            "macd_signal": tf_1d["macd"],
            "bull_ob": tf_1d["bull_ob"],
            "bear_ob": tf_1d["bear_ob"],
            "bull_fvg": tf_1d["bull_fvg"],
            "sl": tf_1d["sl"],
            "tp1": tf_1d["tp1"],
            "tp2": tf_1d["tp2"],
            "risk_pct": tf_1d["risk_pct"],
            "rr": tf_1d["rr"],
            "liq_sweep":  tf_1d["liq_sweep"],
            "setup_type": tf_1d.get("setup_type", "STANDART"),
            "tf_4h": tf_4h,
            "tf_1d": tf_1d,
            "tf_1w": tf_1w,
            "tf_1mo": tf_1mo,
            "action_4h":  action_4h,
            "action_1d":  action_1d,
            "action_1w":  action_1w,
            "action_1mo": action_1mo,
            "stats": stats,
            "ai_score": ai_score,
            "ai_action": action,
            "bullets": bullets[:4],
            "fundamentals": fundamentals,
            "fund_score": fund_score,
            "fund_verdict": fund_verdict,
            "fund_reasons": fund_reasons,
            "whale":   whale,
            "news":    news,
            "insider": insider,
            "error":   None,
        }

    except Exception as e:
        return {"ticker": ticker, "error": str(e)}
