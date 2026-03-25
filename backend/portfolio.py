"""
Portföy Analiz Motoru — Kurumsal Analiz Çerçeveleri
Goldman Sachs • Morgan Stanley • Bridgewater • JPMorgan • BlackRock
Citadel • Renaissance • Two Sigma
"""

import asyncio
import numpy as np
import pandas as pd
import yfinance as yf
from analyzer import analyze_stock, _fundamentals, _rsi, _macd, _ema, _atr


# ─── Temel Veri Toplama ──────────────────────────────────────────────────────

def fetch_portfolio_data(holdings: list[dict]) -> dict:
    """Her holding için yfinance + analiz verisi çek (paralel)."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _fetch_one(h):
        ticker   = h["ticker"].upper()
        shares   = float(h.get("shares", 0))
        avg_cost = float(h.get("avg_cost", 0))
        data = analyze_stock(ticker)
        if not data or data.get("error"):
            return None
        price   = data["price"]
        value   = round(price * shares, 2)
        cost    = round(avg_cost * shares, 2)
        pnl     = round(value - cost, 2)
        pnl_pct = round((price - avg_cost) / avg_cost * 100, 2) if avg_cost > 0 else 0.0
        return (ticker, {
            "ticker":   ticker,
            "price":    price,
            "shares":   shares,
            "avg_cost": avg_cost,
            "value":    value,
            "cost":     cost,
            "pnl":      pnl,
            "pnl_pct":  pnl_pct,
            "analysis": data,
            "fund":     data.get("fundamentals") or {},
        })

    stock_data = {}
    with ThreadPoolExecutor(max_workers=min(4, len(holdings))) as ex:
        futures = {ex.submit(_fetch_one, h): h for h in holdings}
        for fut in as_completed(futures):
            result = fut.result()
            if result:
                stock_data[result[0]] = result[1]

    total_value = sum(v["value"] for v in stock_data.values())
    for t in stock_data:
        stock_data[t]["weight"] = round(
            stock_data[t]["value"] / total_value * 100, 1
        ) if total_value > 0 else 0

    return {"stocks": stock_data, "total_value": round(total_value, 2)}


# ─── Framework Hesaplamaları ─────────────────────────────────────────────────

def calc_gs_fundamental(data: dict) -> dict:
    """Goldman Sachs — Temel Analiz"""
    stocks = data["stocks"]
    rows = []
    total_value = data["total_value"]

    for ticker, s in stocks.items():
        f = s["fund"]
        tf = s["analysis"].get("tf_1d") or {}
        w  = s["weight"]

        rows.append({
            "ticker":     ticker,
            "weight":     w,
            "fk":         f.get("fk"),
            "pd_dd":      f.get("pd_dd"),
            "roe":        f.get("roe"),
            "net_margin": f.get("net_kar_marji"),
            "rev_growth": f.get("gelir_buyume"),
            "debt_eq":    f.get("borc_ozkaynak"),
            "mktcap":     f.get("piyasa_degeri"),
            "fund_score": s["analysis"].get("fund_score"),
            "action":     s["analysis"].get("ai_action"),
            "ai_score":   s["analysis"].get("ai_score"),
            "pnl_pct":    s["pnl_pct"],
        })

    # Portföy ağırlıklı F/K ve diğer ortalamalar
    def wavg(field):
        vals = [(r["weight"], r[field]) for r in rows if r[field] is not None]
        if not vals: return None
        tw = sum(w for w, _ in vals)
        return round(sum(w * v for w, v in vals) / tw, 2) if tw > 0 else None

    return {
        "rows":      rows,
        "port_fk":   wavg("fk"),
        "port_pddd": wavg("pd_dd"),
        "port_roe":  wavg("roe"),
        "port_net_margin": wavg("net_margin"),
        "port_fund_score": wavg("fund_score"),
        "total_value": total_value,
    }


def calc_ms_technical(data: dict) -> dict:
    """Morgan Stanley — Teknik Analiz"""
    stocks = data["stocks"]
    rows = []
    for ticker, s in stocks.items():
        a  = s["analysis"]
        tf = a.get("tf_1d") or {}
        rows.append({
            "ticker":    ticker,
            "weight":    s["weight"],
            "price":     a["price"],
            "trend":     tf.get("trend"),
            "structure": tf.get("market_structure"),
            "rsi":       tf.get("rsi"),
            "rsi_state": tf.get("rsi_state"),
            "macd_bull": (tf.get("macd") or {}).get("bullish"),
            "ema20":     tf.get("ema20"),
            "ema50":     tf.get("ema50"),
            "ema200":    tf.get("ema200"),
            "atr":       tf.get("atr"),
            "rel_vol":   tf.get("rel_vol"),
            "zone":      tf.get("price_zone"),
            "sl":        tf.get("sl"),
            "tp1":       tf.get("tp1"),
            "tp2":       tf.get("tp2"),
            "rr":        tf.get("rr"),
            "ai_score":  a.get("ai_score"),
            "action":    a.get("ai_action"),
            "weekly_bias": a.get("weekly_bias"),
            "sweep":     (tf.get("liq_sweep") or {}).get("type"),
        })

    bull_count = sum(1 for r in rows if r["trend"] == "BOĞA")
    ms_count   = sum(1 for r in rows if r["structure"] == "YUKSELIS")
    return {
        "rows":       rows,
        "bull_count": bull_count,
        "ms_count":   ms_count,
        "total":      len(rows),
    }


def calc_bridgewater_risk(data: dict) -> dict:
    """Bridgewater — Risk Değerlendirmesi"""
    stocks = data["stocks"]

    # Günlük getiri verisi çek
    returns = {}
    for ticker, s in stocks.items():
        try:
            t_obj = yf.Ticker(ticker + ".IS")
            df = t_obj.history(period="6mo", interval="1d", auto_adjust=True)
            if df is not None and len(df) > 20:
                r = df["Close"].pct_change().dropna()
                returns[ticker] = r
        except Exception:
            pass

    # BIST100 benchmark
    try:
        bist = yf.Ticker("XU100.IS")
        df_b = bist.history(period="6mo", interval="1d", auto_adjust=True)
        bist_ret = df_b["Close"].pct_change().dropna() if df_b is not None and len(df_b) > 20 else None
    except Exception:
        bist_ret = None

    rows = []
    for ticker, s in stocks.items():
        r = returns.get(ticker)
        metrics = {}
        if r is not None and len(r) > 20:
            metrics["vol_annual"]   = round(float(r.std() * np.sqrt(252) * 100), 2)
            metrics["max_drawdown"] = round(float(_max_drawdown(r) * 100), 2)
            if bist_ret is not None:
                aligned = r.align(bist_ret, join="inner")
                if len(aligned[0]) > 20:
                    cov = np.cov(aligned[0], aligned[1])
                    beta = round(float(cov[0][1] / cov[1][1]), 2) if cov[1][1] != 0 else 1.0
                    metrics["beta"] = beta
            sharpe = float(r.mean() / r.std() * np.sqrt(252)) if r.std() > 0 else 0
            metrics["sharpe"] = round(sharpe, 2)
        rows.append({
            "ticker":  ticker,
            "weight":  s["weight"],
            "pnl_pct": s["pnl_pct"],
            **metrics,
        })

    # Sektor konsantrasyonu (sektör bilgisi yoksa endüstri adına göre)
    sector_map = {}
    for ticker, s in stocks.items():
        sec = s["fund"].get("sektor") or s["fund"].get("endustri") or "Bilinmiyor"
        sector_map[sec] = sector_map.get(sec, 0) + s["weight"]

    # Portföy toplam volatilitesi (basit — korelasyon yok)
    weights = np.array([s["weight"] / 100 for s in stocks.values()])
    vols    = [r.get("vol_annual", 20.0) for r in rows]
    port_vol = round(float(np.sqrt(np.dot(weights**2, [v**2 for v in vols]))), 2)

    hhi = sum((w / 100) ** 2 for w in sector_map.values()) if sector_map else 1.0
    concentration = "Yüksek" if hhi > 0.25 else "Orta" if hhi > 0.15 else "Düşük"

    return {
        "rows":          rows,
        "port_vol":      port_vol,
        "sectors":       sector_map,
        "n_stocks":      len(rows),
        "n_sectors":     len(sector_map),
        "concentration": concentration,
        "hhi":           round(hhi, 3),
    }


def calc_blackrock_dividend(data: dict) -> dict:
    """BlackRock — Temettü Geliri Analizi"""
    stocks = data["stocks"]
    rows   = []
    total  = data["total_value"]

    for ticker, s in stocks.items():
        f = s["fund"]
        yield_pct = f.get("temttu_verimi") or 0
        payout    = None
        if f.get("eps") and f.get("eps") > 0:
            # dividendRate / EPS — rough payout ratio
            pass
        annual_income = round(s["value"] * yield_pct / 100, 2) if yield_pct else 0
        rows.append({
            "ticker":        ticker,
            "weight":        s["weight"],
            "value":         s["value"],
            "yield_pct":     yield_pct,
            "annual_income": annual_income,
        })

    total_income = round(sum(r["annual_income"] for r in rows), 2)
    port_yield   = round(total_income / total * 100, 2) if total > 0 else 0

    # 10 yıllık gelir projeksiyonu (yıllık %5 büyüme varsayımı)
    projection = []
    income = total_income
    for yr in range(1, 11):
        income *= 1.05
        projection.append({"year": yr, "income": round(income, 2)})

    return {
        "rows":         rows,
        "total_income": total_income,
        "port_yield":   port_yield,
        "projection":   projection,
    }


def calc_citadel_sector(data: dict) -> dict:
    """Citadel — Sektör Dağılımı"""
    stocks = data["stocks"]
    sector_data = {}

    for ticker, s in stocks.items():
        sec  = s["fund"].get("sektor") or "Diğer"
        ind  = s["fund"].get("endustri") or sec
        key  = sec
        if key not in sector_data:
            sector_data[key] = {"sector": sec, "weight": 0, "tickers": [], "avg_score": 0, "scores": []}
        sector_data[key]["weight"]  += s["weight"]
        sector_data[key]["tickers"].append(ticker)
        sc = s["analysis"].get("ai_score") or 0
        sector_data[key]["scores"].append(sc)

    for k in sector_data:
        sc = sector_data[k]["scores"]
        sector_data[k]["avg_score"] = round(sum(sc) / len(sc), 1) if sc else 0
        del sector_data[k]["scores"]

    hhi = sum((v["weight"] / 100) ** 2 for v in sector_data.values())
    concentration = "Yüksek" if hhi > 0.25 else "Orta" if hhi > 0.15 else "Düşük"

    rows = sorted(sector_data.values(), key=lambda x: x["weight"], reverse=True)
    return {
        "rows":          rows,
        "hhi":           round(hhi, 3),
        "concentration": concentration,
        "n_sectors":     len(rows),
    }


def calc_renaissance_quant(data: dict) -> dict:
    """Renaissance Technologies — Kantitatif Tarama"""
    stocks = data["stocks"]
    rows   = []

    for ticker, s in stocks.items():
        a  = s["analysis"]
        f  = s["fund"]
        tf = a.get("tf_1d") or {}

        # Değer faktörü (0–25)
        val_score = 0
        fk = f.get("fk")
        if fk and 0 < fk < 10: val_score += 15
        elif fk and fk < 20:   val_score += 10
        elif fk and fk < 30:   val_score += 5

        pd_dd = f.get("pd_dd")
        if pd_dd and pd_dd < 1:   val_score += 10
        elif pd_dd and pd_dd < 2: val_score += 7
        elif pd_dd and pd_dd < 4: val_score += 3

        # Kalite faktörü (0–25)
        qual_score = 0
        roe = f.get("roe")
        if roe and roe > 25:   qual_score += 10
        elif roe and roe > 15: qual_score += 7
        elif roe and roe > 5:  qual_score += 4

        nm = f.get("net_kar_marji")
        if nm and nm > 20:   qual_score += 8
        elif nm and nm > 10: qual_score += 5
        elif nm and nm > 0:  qual_score += 2

        d_e = f.get("borc_ozkaynak")
        if d_e is not None and d_e < 30: qual_score += 7
        elif d_e is not None and d_e < 70: qual_score += 4

        # Momentum faktörü (0–25)
        mom_score = 0
        if tf.get("market_structure") == "YUKSELIS": mom_score += 10
        rsi = tf.get("rsi") or 50
        if 40 <= rsi <= 65: mom_score += 8
        elif rsi < 40:      mom_score += 5
        macd_bull = (tf.get("macd") or {}).get("bullish")
        if macd_bull:       mom_score += 7

        # Büyüme faktörü (0–25)
        grow_score = 0
        rg = f.get("gelir_buyume")
        if rg and rg > 20:   grow_score += 15
        elif rg and rg > 10: grow_score += 10
        elif rg and rg > 0:  grow_score += 5

        eg = f.get("kar_buyume")
        if eg and eg > 15:   grow_score += 10
        elif eg and eg > 5:  grow_score += 6
        elif eg and eg > 0:  grow_score += 2

        composite = round((val_score + qual_score + mom_score + grow_score) / 100 * 10, 1)
        rows.append({
            "ticker":     ticker,
            "weight":     s["weight"],
            "val_score":  val_score,
            "qual_score": qual_score,
            "mom_score":  mom_score,
            "grow_score": grow_score,
            "composite":  composite,
            "action":     a.get("ai_action"),
            "ai_score":   a.get("ai_score"),
        })

    rows.sort(key=lambda x: x["composite"], reverse=True)
    return {"rows": rows}


def calc_jpmorgan_earnings(data: dict) -> dict:
    """JPMorgan — Kazanç Analizi"""
    stocks = data["stocks"]
    rows   = []

    for ticker, s in stocks.items():
        f  = s["fund"]
        a  = s["analysis"]
        tf = a.get("tf_1d") or {}

        # Basit kazanç büyümesi metrikleri (gerçek kazanç tarihine erişim sınırlı)
        rows.append({
            "ticker":    ticker,
            "weight":    s["weight"],
            "eps":       f.get("eps"),
            "fk":        f.get("fk"),
            "fk_fwd":    f.get("fk_forward"),
            "kar_buyume": f.get("kar_buyume"),
            "rev_growth": f.get("gelir_buyume"),
            "action":    a.get("ai_action"),
            "ai_score":  a.get("ai_score"),
            "rsi":       tf.get("rsi"),
        })

    return {"rows": rows}


# ─── Yardımcı ────────────────────────────────────────────────────────────────

def _max_drawdown(returns: pd.Series) -> float:
    cumret = (1 + returns).cumprod()
    peak   = cumret.cummax()
    dd     = (cumret - peak) / peak
    return float(dd.min())






# ─── Deterministik Rapor Üreticileri (API kullanmaz) ─────────────────────────

def _na(v, suffix="", decimals=2):
    """None ise '—', aksi hâlde formatlanmış string döndür."""
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{round(v, decimals)}{suffix}"
    return f"{v}{suffix}"


def _report_gs(ticker: str, price: float, fund: dict, fund_score, ai_score: float, action: str) -> str:
    """Goldman Sachs — Temel Analiz (deterministik)."""
    f = fund
    sector   = f.get('sektor')   or 'Bilinmiyor'
    industry = f.get('endustri') or sector
    fk, fk_fwd, pd_dd = f.get('fk'), f.get('fk_forward'), f.get('pd_dd')
    roe, roa  = f.get('roe'),  f.get('roa')
    nm,  gm   = f.get('net_kar_marji'), f.get('brut_kar_marji')
    rg,  eg   = f.get('gelir_buyume'),  f.get('kar_buyume')
    de,  cr   = f.get('borc_ozkaynak'), f.get('cari_oran')
    div       = f.get('temttu_verimi')
    mktcap    = f.get('piyasa_degeri') or '—'
    eps       = f.get('eps')

    out = [f"## {ticker} — Goldman Sachs Equity Research\n**Sektör:** {sector}  |  **Endüstri:** {industry}  |  **Piyasa Değeri:** {mktcap}\n---\n"]

    # 1. Değerleme
    out.append("### 📊 1. Değerleme Analizi")
    vl = []
    if fk is not None:
        if   fk < 0:   vl.append(f"F/K negatif ({fk}x) — şirket zarar yazıyor, çarpan anlamlı değil.")
        elif fk < 8:   vl.append(f"F/K {fk}x — BIST tarihsel ortalamasının ({8}–{15}x) belirgin altında; derin değer fırsatı.")
        elif fk < 15:  vl.append(f"F/K {fk}x — makul değerleme bandında, büyüme için ödül/risk dengesi cazip.")
        elif fk < 25:  vl.append(f"F/K {fk}x — hafif premium değerleme; büyüme beklentisi fiyatlanmış.")
        else:          vl.append(f"F/K {fk}x — yüksek çarpan; beklentilerin karşılanmaması hâlinde sert düzeltme riski.")
    if fk_fwd is not None and fk is not None and fk_fwd > 0:
        if fk_fwd < fk: vl.append(f"İleriye dönük F/K {fk_fwd}x ile gerileyerek beklenen kazanç artışına işaret ediyor.")
        else:           vl.append(f"İleriye dönük F/K {fk_fwd}x — kazanç büyümesinin yavaşlayabileceğine dikkat.")
    if pd_dd is not None:
        if   pd_dd < 1: vl.append(f"PD/DD {pd_dd}x — defter değerinin altında işlem görüyor (derin iskonto).")
        elif pd_dd < 2: vl.append(f"PD/DD {pd_dd}x — defter değerine yakın, makul.")
        elif pd_dd < 4: vl.append(f"PD/DD {pd_dd}x — güçlü karlılık veya marka değeri prim oluşturuyor.")
        else:           vl.append(f"PD/DD {pd_dd}x — yüksek prim; yatırımcı güçlü büyüme öngörüyor.")
    out.append(" ".join(vl) if vl else "Değerleme verisi yetersiz.")
    out.append("")

    # 2. Karlılık
    out.append("### 💹 2. Karlılık & Sermaye Verimliliği")
    pl = []
    if roe is not None:
        if   roe > 25: pl.append(f"ROE %{roe} — olağanüstü sermaye verimliliği, güçlü rekabet avantajı.")
        elif roe > 15: pl.append(f"ROE %{roe} — kurumsal yatırım eşiği (%15) üzerinde, kaliteli bilanço.")
        elif roe > 8:  pl.append(f"ROE %{roe} — orta düzey; gelişme potansiyeli var.")
        elif roe > 0:  pl.append(f"ROE %{roe} — düşük sermaye getirisi; operasyonel iyileşme gerekiyor.")
        else:          pl.append(f"ROE %{roe} — negatif; özkaynak erozyonu sinyali.")
    if nm is not None:
        if   nm > 20: pl.append(f"Net kar marjı %{nm} — sektör üst bandında güçlü karlılık.")
        elif nm > 10: pl.append(f"Net kar marjı %{nm} — sağlıklı karlılık profili.")
        elif nm > 0:  pl.append(f"Net kar marjı %{nm} — baskı altında; marj genişlemesi takip edilmeli.")
        else:         pl.append(f"Net kar marjı %{nm} — zarar bölgesinde; kırılma noktası izlenmeli.")
    if gm is not None:
        pl.append(f"Brüt kar marjı %{gm}.")
    if roa is not None:
        pl.append(f"ROA %{roa} ({'güçlü varlık getirisi' if roa > 5 else 'düşük varlık getirisi'}).")
    if eps is not None:
        pl.append(f"Hisse başı kâr ₺{eps}.")
    out.append(" ".join(pl) if pl else "Karlılık verisi yetersiz.")
    out.append("")

    # 3. Bilanço
    out.append("### 🏦 3. Bilanço Sağlığı")
    bl = []
    if de is not None:
        if   de < 30:  bl.append(f"Borç/Özkaynak %{de} — güçlü bilanço, düşük finansal kaldıraç.")
        elif de < 70:  bl.append(f"Borç/Özkaynak %{de} — orta düzey borç yükü, yönetilebilir.")
        elif de < 150: bl.append(f"Borç/Özkaynak %{de} — yüksek kaldıraç; faiz artışlarına karşı hassas.")
        else:          bl.append(f"Borç/Özkaynak %{de} — aşırı borç; finansal risk faktörü.")
    if cr is not None:
        if   cr > 2:   bl.append(f"Cari oran {cr} — güçlü kısa vadeli likidite.")
        elif cr > 1.2: bl.append(f"Cari oran {cr} — yeterli likidite.")
        elif cr > 1:   bl.append(f"Cari oran {cr} — sınırda; dikkatli izlenmeli.")
        else:          bl.append(f"Cari oran {cr} — likidite riski mevcut.")
    out.append(" ".join(bl) if bl else "Bilanço verisi yetersiz.")
    out.append("")

    # 4. Büyüme
    out.append("### 📈 4. Büyüme Görünümü")
    gl = []
    if rg is not None:
        if   rg > 20: gl.append(f"Gelir büyümesi %{rg} — güçlü momentum korunuyor.")
        elif rg > 10: gl.append(f"Gelir büyümesi %{rg} — üst orta büyüme trendi.")
        elif rg > 0:  gl.append(f"Gelir büyümesi %{rg} — ılımlı; enflasyonun gerçek anlamda üzerinde mi takip edilmeli.")
        else:         gl.append(f"Gelir büyümesi %{rg} — daralma; temel sorun sinyali.")
    if eg is not None:
        if   eg > 20: gl.append(f"Kâr büyümesi %{eg} — gelirlerin üzerinde, marj genişlemesi sürüyor.")
        elif eg > 0:  gl.append(f"Kâr büyümesi %{eg} — pozitif.")
        else:         gl.append(f"Kâr büyümesi %{eg} — kâr baskısı var.")
    out.append(" ".join(gl) if gl else "Büyüme verisi yetersiz.")
    out.append("")

    # 5. Temettü
    out.append("### 💰 5. Temettü Politikası")
    if div and div > 0:
        if   div > 5: out.append(f"Temettü verimi %{div} — yüksek nakit dağıtımı; gelir odaklı yatırımcı için cazip.")
        elif div > 2: out.append(f"Temettü verimi %{div} — orta düzey; enflasyon koruması sınırlı.")
        else:         out.append(f"Temettü verimi %{div} — sembolik; şirket büyümeye yatırım yapıyor.")
    else:
        out.append("Temettü ödemesi yok veya veri mevcut değil.")
    out.append("")

    # 6. Tavsiye
    out.append("### 🎯 6. GS Tavsiyesi")
    if   action in ("GÜÇLÜ AL", "AL"): verdict, color = "AŞIRI AĞIRLIK (Overweight) ✅",   "güçlü temel + teknik uyum"
    elif action == "İZLE":             verdict, color = "NÖTR / İZLE (Neutral) 🟡",          "katalist bekleniyor, temkinli takip"
    elif action == "ZAYIF":            verdict, color = "DÜŞÜK AĞIRLIK (Underweight) 🟠",    "zayıflayan momentum ve temel baskı"
    else:                              verdict, color = "SAT (Sell) 🔴",                      "hem teknik hem temel baskı altında"
    fs_txt = f", Temel Skor {fund_score}/10" if fund_score is not None else ""
    out.append(f"AI Skoru {ai_score}/10{fs_txt} → **{verdict}**. Gerekçe: {color}.")
    return "\n".join(out)


def _report_ms(ticker: str, price: float, tf1d: dict, tf4h: dict, tf1w: dict, stats: dict, weekly_bias: str, ai_score: float, action: str) -> str:
    """Morgan Stanley — Teknik Analiz (deterministik)."""
    trend   = tf1d.get('trend')
    struct  = tf1d.get('market_structure')
    rsi     = tf1d.get('rsi')
    rsi_s   = tf1d.get('rsi_state')
    macd    = tf1d.get('macd') or {}
    macd_b  = macd.get('bullish')
    ema20, ema50, ema200 = tf1d.get('ema20'), tf1d.get('ema50'), tf1d.get('ema200')
    atr     = tf1d.get('atr')
    rvol    = tf1d.get('rel_vol')
    zone    = tf1d.get('price_zone')
    sups    = tf1d.get('supports',    [])[:3]
    ress    = tf1d.get('resistances', [])[:3]
    bull_ob = tf1d.get('bull_ob')
    bull_fvg= tf1d.get('bull_fvg')
    sweep   = tf1d.get('liq_sweep')
    bos     = tf1d.get('bos')
    sl, tp1, tp2, rr = tf1d.get('sl'), tf1d.get('tp1'), tf1d.get('tp2'), tf1d.get('rr')
    risk_pct = tf1d.get('risk_pct')

    out = [f"## {ticker} — Morgan Stanley Technical Strategy\n**Fiyat:** ₺{price}  |  **Haftalık Bias:** {weekly_bias}  |  **AI Skoru:** {ai_score}/10\n---\n"]

    # 1. MTF
    out.append("### 🔭 1. Çok Zaman Dilimli Trend Uyumu (MTF)")
    mtf = []
    trends = {
        '4H': tf4h.get('trend'), 'Günlük': trend, 'Haftalık': tf1w.get('trend')
    }
    bull_cnt = sum(1 for v in trends.values() if v == 'BOĞA')
    for tf_name, tr in trends.items():
        if tr:
            mtf.append(f"{tf_name}: {'🐂 Yükseliş' if tr=='BOĞA' else '🐻 Düşüş'}")
    alignment = "Tam yükseliş uyumu — güçlü konjonktür." if bull_cnt == 3 else \
                "Kısmi uyum — orta güven." if bull_cnt == 2 else \
                "Kısmi düşüş baskısı." if bull_cnt == 1 else \
                "Tam düşüş uyumu — zayıf konjonktür."
    out.append("  |  ".join(mtf) + f"\n→ {alignment}")
    out.append("")

    # 2. Piyasa Yapısı
    out.append("### 📐 2. Piyasa Yapısı")
    if struct == 'YUKSELIS':
        out.append(f"Günlük yapı HH/HL yükseliş dizisinde — alıcılar kontrolde.")
    elif struct == 'DUSUS':
        out.append(f"Günlük yapı LH/LL düşüş dizisinde — satıcılar baskın.")
    else:
        out.append(f"Yatay bant yapısı — yön kararı bekleniyor.")
    if bos:
        out.append(f"BOS (Yapı Kırılımı): {bos} sinyali mevcut.")
    out.append("")

    # 3. Momentum
    out.append("### ⚡ 3. Momentum Göstergeleri")
    mom = []
    if rsi is not None:
        if   rsi > 70: mom.append(f"RSI {rsi} (Aşırı Alım) — dikkat, momentum zayıflayabilir.")
        elif rsi < 30: mom.append(f"RSI {rsi} (Aşırı Satım) — toparlanma fırsatı.")
        elif rsi > 55: mom.append(f"RSI {rsi} ({rsi_s}) — momentum güçlü, yükseliş bölgesi.")
        elif rsi < 45: mom.append(f"RSI {rsi} ({rsi_s}) — momentum zayıf.")
        else:          mom.append(f"RSI {rsi} ({rsi_s}) — nötr bölge, yön bekleniyor.")
    if macd_b is not None:
        mom.append(f"MACD {'🟢 Bullish Cross — alım sinyali' if macd_b else '🔴 Bearish — satış baskısı'}.")
    if rvol is not None:
        if   rvol > 1.5: mom.append(f"Relatif hacim {rvol}x — güçlü hacim onayı.")
        elif rvol < 0.7: mom.append(f"Relatif hacim {rvol}x — zayıf hacim, hareket onaylanmamış.")
        else:            mom.append(f"Relatif hacim {rvol}x — normal.")
    out.append(" ".join(mom) if mom else "Momentum verisi yetersiz.")
    out.append("")

    # 4. SMC (Order Block / FVG / Sweep)
    out.append("### 🧩 4. SMC — Kurumsal Para İzleri")
    smc = []
    if bull_ob:
        smc.append(f"Bullish Order Block: ₺{bull_ob.get('low')}–₺{bull_ob.get('high')} ({bull_ob.get('date')}) — talep bölgesi, büyük alıcı iz bırakmış.")
    if bull_fvg:
        smc.append(f"Bullish FVG: ₺{bull_fvg.get('low')}–₺{bull_fvg.get('high')} ({bull_fvg.get('date')}) — doldurulamayan boşluk, mıknatıs seviyesi.")
    if sweep:
        smc.append(f"Likidite Sweep: {sweep.get('type')} @ ₺{sweep.get('price')} ({sweep.get('date')}) — fiyat stop avı yapıp döndü.")
    if not smc:
        smc.append("Aktif SMC izi mevcut değil.")
    out.append("\n".join(smc))
    out.append("")

    # 5. Kritik Seviyeler
    out.append("### 🧱 5. Kritik Fiyat Seviyeleri")
    if ress:
        out.append(f"**Direnç:** {' → '.join([f'₺{r}' for r in ress])}")
    out.append(f"**Mevcut:** ₺{price}")
    if sups:
        out.append(f"**Destek:** {' → '.join([f'₺{s}' for s in sups])}")
    if ema20: out.append(f"EMA20: ₺{ema20}  {'✅ fiyat üstünde' if price > ema20 else '⚠ fiyat altında'}")
    if ema50: out.append(f"EMA50: ₺{ema50}  {'✅' if price > ema50 else '⚠'}")
    if ema200: out.append(f"EMA200: ₺{ema200}  {'✅ uzun vadeli yükseliş' if price > ema200 else '⚠ uzun vadeli baskı'}")
    out.append("")

    # 6. İşlem Planı
    out.append("### 🎯 6. İşlem Planı")
    rr_ok = rr is not None and rr >= 2
    out.append(f"| | Seviye |")
    out.append(f"|---|---|")
    out.append(f"| 📍 Fiyat   | ₺{price} |")
    out.append(f"| 🛑 ZK      | ₺{_na(sl)} |")
    out.append(f"| 🎯 Hedef 1 | ₺{_na(tp1)} |")
    out.append(f"| 🏆 Hedef 2 | ₺{_na(tp2)} |")
    out.append(f"| ⚖ R:R     | 1:{_na(rr)} {'✅' if rr_ok else '⚠ yetersiz'} |")
    out.append(f"| ⚠ Risk    | %{_na(risk_pct)} sermaye |")
    if zone:
        out.append(f"\nFiyat bölgesi: **{'🔴 Premium (pahalı bölge)' if zone=='PAHALI' else '🟢 Discount (iskontolu bölge)'}**.")
    out.append("")

    # 7. MS Görüşü
    out.append("### 🏦 7. MS Teknik Görüşü")
    ms_v = "teknik yapı güçlü, alım bölgesine yakın" if action in ("GÜÇLÜ AL","AL") else \
           "kararsız yapı, net sinyal bekleniyor" if action=="İZLE" else "zayıflayan yapı, temkinli ol"
    out.append(f"Mevcut yapı → **{ms_v}**. Haftalık bias {weekly_bias}, MTF {bull_cnt}/3 yükseliş uyumu.")
    return "\n".join(out)


def _report_bw(ticker: str, price: float, tf1d: dict, fund: dict, stats: dict, ai_score: float, action: str) -> str:
    """Bridgewater — Risk Değerlendirmesi (deterministik)."""
    atr      = tf1d.get('atr')
    rvol     = tf1d.get('rel_vol')
    zone     = tf1d.get('price_zone')
    sl       = tf1d.get('sl')
    rr       = tf1d.get('rr')
    struct   = tf1d.get('market_structure')
    avg_move = stats.get('avg_daily_range_pct')
    de  = fund.get('borc_ozkaynak')
    cr  = fund.get('cari_oran')
    nm  = fund.get('net_kar_marji')
    rg  = fund.get('gelir_buyume')

    out = [f"## {ticker} — Bridgewater Risk Değerlendirmesi\n**Fiyat:** ₺{price}  |  **AI Skoru:** {ai_score}/10\n---\n"]

    # 1. Volatilite
    out.append("### 📊 1. Volatilite Profili")
    vl = []
    if atr is not None and price > 0:
        atr_pct = round(atr / price * 100, 2)
        if   atr_pct > 5: vl.append(f"ATR %{atr_pct} — yüksek volatilite; pozisyon boyutu küçük tutulmalı.")
        elif atr_pct > 2: vl.append(f"ATR %{atr_pct} — orta volatilite; standart pozisyon uygun.")
        else:             vl.append(f"ATR %{atr_pct} — düşük volatilite; daha büyük pozisyon taşınabilir.")
    if avg_move:
        vl.append(f"Ortalama günlük hareket %{avg_move}.")
    out.append(" ".join(vl) if vl else "Volatilite verisi yetersiz.")
    out.append("")

    # 2. Likidite
    out.append("### 💧 2. Likidite Riski")
    if rvol is not None:
        if   rvol > 2:   out.append(f"Relatif hacim {rvol}x — çok yüksek; ani fiyat hareketine dikkat.")
        elif rvol > 1.2: out.append(f"Relatif hacim {rvol}x — normalin üzerinde; likidite yeterli.")
        elif rvol > 0.7: out.append(f"Relatif hacim {rvol}x — normal; giriş/çıkış kolaylığı orta.")
        else:            out.append(f"Relatif hacim {rvol}x — düşük hacim; büyük emirlerde kayma riski.")
    else:
        out.append("Hacim verisi yetersiz.")
    out.append("")

    # 3. Downside
    out.append("### 📉 3. Downside Riski")
    dl = []
    if sl is not None and price > 0:
        sl_pct = round((price - sl) / price * 100, 2)
        if sl_pct > 10:
            dl.append(f"ZK ₺{sl} — mevcut fiyattan %{sl_pct} uzakta; geniş stop, risk yüksek.")
        elif sl_pct > 5:
            dl.append(f"ZK ₺{sl} — mevcut fiyattan %{sl_pct} uzakta; orta mesafeli stop.")
        else:
            dl.append(f"ZK ₺{sl} — mevcut fiyattan %{sl_pct} uzakta; sıkı stop, fiyat dalgalanmasında tetiklenebilir.")
    if zone == 'PAHALI':
        dl.append("Fiyat premium bölgede; retracement olasılığı yüksek, düşüş için daha fazla alan var.")
    else:
        dl.append("Fiyat discount bölgede; potansiyel downside sınırlı, risk/ödül dengesi uygun.")
    if rr is not None:
        dl.append(f"R:R 1:{rr} — {'tatmin edici' if rr >= 2 else 'yetersiz, daha iyi giriş bekle'}.")
    out.append(" ".join(dl) if dl else "Downside verisi yetersiz.")
    out.append("")

    # 4. Temel Riskler
    out.append("### ⚠️ 4. Temel Risk Faktörleri")
    risks = []
    if de is not None and de > 100: risks.append(f"🔴 Borç/Özkaynak %{de} — aşırı kaldıraç.")
    elif de is not None and de > 70: risks.append(f"🟠 Borç/Özkaynak %{de} — yüksek borç yükü.")
    if cr is not None and cr < 1:   risks.append(f"🔴 Cari oran {cr} — kısa vadeli likidite riski.")
    elif cr is not None and cr < 1.2: risks.append(f"🟠 Cari oran {cr} — sınırda likidite.")
    if nm is not None and nm < 0:   risks.append(f"🔴 Net kar marjı %{nm} — zarar yazıyor.")
    elif nm is not None and nm < 5: risks.append(f"🟠 Net kar marjı %{nm} — düşük karlılık.")
    if rg is not None and rg < 0:   risks.append(f"🔴 Gelir büyümesi %{rg} — daralma sinyali.")
    if struct == 'DUSUS':           risks.append("🟠 Günlük yapı düşüşte — teknik baskı.")
    if not risks:
        out.append("✅ Belirgin temel risk faktörü tespit edilmedi.")
    else:
        out.append("\n".join(risks))
    out.append("")

    # 5. Pozisyon Önerisi
    out.append("### 🎛️ 5. Risk Kontrolü & Pozisyon Büyüklüğü")
    risk_count = len([r for r in risks if r.startswith("🔴")])
    if   action in ("GÜÇLÜ AL", "AL") and risk_count == 0: max_w = "maks. **%8–10** portföy ağırlığı"
    elif action in ("GÜÇLÜ AL", "AL"):                      max_w = "maks. **%5–7** portföy ağırlığı"
    elif action == "İZLE":                                   max_w = "maks. **%3–5** portföy ağırlığı (izle, tam pozisyon kurma)"
    else:                                                    max_w = "**pozisyon kaçın** veya maks. %2 savunma amaçlı"
    out.append(f"Bridgewater risk çerçevesine göre {max_w} önerilir.")
    if atr is not None and price > 0:
        lot_hint = round(1000 / (atr / price * 100), 0)
        out.append(f"₺1.000 risk için tahmini lot: {int(lot_hint)} adet (ATR bazlı).")
    return "\n".join(out)


def _report_two_sigma(ticker: str, price: float, fund: dict, tf1d: dict, tf4h: dict, tf1w: dict,
                      stats: dict, weekly_bias: str, ai_score: float, action: str) -> str:
    """Two Sigma — Kantitatif & Makro (deterministik)."""
    f = fund
    sector  = f.get('sektor')   or 'Bilinmiyor'
    fk      = f.get('fk')
    pd_dd   = f.get('pd_dd')
    roe     = f.get('roe')
    nm      = f.get('net_kar_marji')
    de      = f.get('borc_ozkaynak')
    rg      = f.get('gelir_buyume')
    eg      = f.get('kar_buyume')
    div     = f.get('temttu_verimi')
    best_days  = stats.get('best_days',  [])
    best_hours = stats.get('best_hours', [])
    avg_move   = stats.get('avg_daily_range_pct')

    # Faktör skorları
    val_s = 0
    if fk   and 0 < fk < 10:   val_s += 15
    elif fk and fk < 20:        val_s += 10
    elif fk and fk < 30:        val_s += 5
    if pd_dd and pd_dd < 1:    val_s += 10
    elif pd_dd and pd_dd < 2:  val_s += 7
    elif pd_dd and pd_dd < 4:  val_s += 3

    qual_s = 0
    if roe and roe > 25:       qual_s += 10
    elif roe and roe > 15:     qual_s += 7
    elif roe and roe > 5:      qual_s += 4
    if nm and nm > 20:         qual_s += 8
    elif nm and nm > 10:       qual_s += 5
    elif nm and nm > 0:        qual_s += 2
    if de is not None and de < 30:  qual_s += 7
    elif de is not None and de < 70: qual_s += 4

    mom_s = 0
    if tf1d.get('market_structure') == 'YUKSELIS': mom_s += 10
    rsi = tf1d.get('rsi') or 50
    if 40 <= rsi <= 65: mom_s += 8
    elif rsi < 40:      mom_s += 5
    if (tf1d.get('macd') or {}).get('bullish'): mom_s += 7

    grow_s = 0
    if rg and rg > 20:   grow_s += 15
    elif rg and rg > 10: grow_s += 10
    elif rg and rg > 0:  grow_s += 5
    if eg and eg > 15:   grow_s += 10
    elif eg and eg > 5:  grow_s += 6
    elif eg and eg > 0:  grow_s += 2

    composite = round((val_s + qual_s + mom_s + grow_s) / 100 * 10, 1)

    out = [f"## {ticker} — Two Sigma Kantitatif Analiz\n**Sektör:** {sector}  |  **Fiyat:** ₺{price}  |  **Haftalık Bias:** {weekly_bias}\n---\n"]

    # 1. Faktör Tablosu
    out.append("### 🔢 1. Faktör Modeli Sonuçları")
    out.append(f"| Faktör | Skor | Azami |")
    out.append(f"|---|---|---|")
    out.append(f"| 💎 Değer (F/K + PD/DD) | {val_s} | 25 |")
    out.append(f"| 🏆 Kalite (ROE + Marj + Borç) | {qual_s} | 25 |")
    out.append(f"| ⚡ Momentum (Yapı + RSI + MACD) | {mom_s} | 25 |")
    out.append(f"| 📈 Büyüme (Gelir + Kâr) | {grow_s} | 25 |")
    out.append(f"| **Kompozit Skor** | **{composite}/10** | 10 |")
    out.append("")

    # 2. Faktör yorumları
    out.append("### 🔍 2. Faktör Analizi")
    fa = []
    dominant = max([("Değer", val_s), ("Kalite", qual_s), ("Momentum", mom_s), ("Büyüme", grow_s)], key=lambda x: x[1])
    weakest  = min([("Değer", val_s), ("Kalite", qual_s), ("Momentum", mom_s), ("Büyüme", grow_s)], key=lambda x: x[1])
    fa.append(f"**En güçlü faktör: {dominant[0]}** ({dominant[1]}/25). {'' if dominant[1] >= 15 else 'Orta güçte.'}")
    fa.append(f"**En zayıf faktör: {weakest[0]}** ({weakest[1]}/25) — geliştirme alanı.")
    if val_s >= 18:   fa.append("Değerleme cazip; düşük F/K ve/veya PD/DD ile pozitif alfa potansiyeli.")
    elif val_s <= 5:  fa.append("Değerleme pahalı; yüksek çarpanlar alfa potansiyelini kısıtlıyor.")
    if qual_s >= 18:  fa.append("Kalite yüksek; güçlü ROE ve düşük borç sürdürülebilir getiri sağlar.")
    elif qual_s <= 7: fa.append("Kalite düşük; marj veya borç baskısı uzun vadeli getirileri olumsuz etkileyebilir.")
    if mom_s >= 18:   fa.append("Momentum güçlü; teknik yapı alım yönünde.")
    elif mom_s <= 7:  fa.append("Momentum zayıf; trendin döneceği beklenene kadar girişten kaçınılabilir.")
    out.append("\n".join(fa))
    out.append("")

    # 3. Mevsimsellik
    out.append("### 📅 3. Mevsimsellik & Zamanlama")
    if best_days:
        out.append(f"Tarihsel olarak en hareketli günler: **{', '.join(best_days)}**.")
    if best_hours:
        out.append(f"En aktif saatler: **{', '.join(str(h) for h in best_hours)}** — bu saatlerde likidite yüksek, spread düşük.")
    if avg_move:
        out.append(f"Ortalama günlük hareket: **%{avg_move}** — günlük fiyat hedefi belirlenmesinde kullanılabilir.")
    out.append("")

    # 4. MTF Uyum
    out.append("### 📡 4. Çok Zaman Dilimli Uyum")
    tf_trends = [
        ("4H",      tf4h.get('trend'), tf4h.get('rsi')),
        ("Günlük",  tf1d.get('trend'), tf1d.get('rsi')),
        ("Haftalık",tf1w.get('trend'), tf1w.get('rsi')),
    ]
    for name, tr, r in tf_trends:
        if tr:
            icon = "🐂" if tr == "BOĞA" else "🐻"
            out.append(f"{name}: {icon} {tr}  RSI: {_na(r)}")
    out.append("")

    # 5. Özet
    out.append("### 🎯 5. İki-Sigma Kompozit Görüş")
    if   composite >= 7:  qual = "GÜÇLÜ AL — çoklu faktör uyumu mevcut"
    elif composite >= 5:  qual = "NÖTR / İZLE — karışık sinyaller"
    elif composite >= 3:  qual = "ZAYIF — temel veya momentum baskısı"
    else:                 qual = "SAT — faktör modeli olumsuz"
    out.append(f"Kompozit {composite}/10 → **{qual}**.")
    if div and div > 3:
        out.append(f"Ek getiri: %{div} temettü verimi portföy getirisini destekliyor.")
    return "\n".join(out)


# ─── Tek Hisse Derin Analizi ─────────────────────────────────────────────────

async def single_stock_deep_analysis(ticker: str) -> dict:
    """Tek bir hisse için kurumsal analizi — API çağrısı yok, deterministik."""
    from concurrent.futures import ThreadPoolExecutor

    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=1) as ex:
        data = await loop.run_in_executor(ex, analyze_stock, ticker)

    if not data or data.get("error"):
        return {"error": data.get("error") if data else "Veri alınamadı"}

    tf1d = data.get("tf_1d") or {}
    tf1w = data.get("tf_1w") or {}
    tf4h = data.get("tf_4h") or {}
    fund       = data.get("fundamentals") or {}
    price      = data.get("price", 0)
    ai_score   = data.get("ai_score", 0)
    fund_score = data.get("fund_score")
    action     = data.get("ai_action", "")
    weekly_bias = data.get("weekly_bias", "Nötr")
    stats      = data.get("stats") or {}

    ai_out = {
        "gs_stock":        _report_gs(ticker, price, fund, fund_score, ai_score, action),
        "ms_stock":        _report_ms(ticker, price, tf1d, tf4h, tf1w, stats, weekly_bias, ai_score, action),
        "bw_stock":        _report_bw(ticker, price, tf1d, fund, stats, ai_score, action),
        "two_sigma_stock": _report_two_sigma(ticker, price, fund, tf1d, tf4h, tf1w, stats, weekly_bias, ai_score, action),
    }

    return {
        "ticker":      ticker,
        "price":       price,
        "ai_score":    ai_score,
        "action":      action,
        "ai_analysis": ai_out,
    }


# ─── Format Yardımcıları ─────────────────────────────────────────────────────

def _build_port_summary(computed: dict) -> str:
    gs = computed["gs_fundamental"]
    tickers = list(computed.get("raw", {}).get("stocks", {}).keys())
    return (
        f"Hisseler: {', '.join(tickers)} | "
        f"Toplam Değer: ₺{computed['raw']['total_value']:,.0f} | "
        f"Ort. F/K: {gs.get('port_fk')} | "
        f"Ort. ROE: %{gs.get('port_roe')} | "
        f"Temel Skor: {gs.get('port_fund_score')}/10"
    )

def _fmt_gs(gs: dict, raw: dict = None) -> str:
    rows = gs.get("rows", [])
    stocks = (raw or {}).get("stocks", {})
    lines = []
    for r in rows:
        f = stocks.get(r["ticker"], {}).get("fund", {}) if stocks else {}
        ebitda    = f.get("ebitda")
        net_gelir = f.get("net_gelir")
        ozkaynak  = f.get("ozkaynak")
        hisse_say = f.get("hisse_sayisi")
        top_gelir = f.get("toplam_gelir")
        mktcap    = f.get("piyasa_degeri") or r.get("mktcap", "?")
        ebitda_str = f"{ebitda/1e6:.0f}Mn₺" if ebitda else "?"
        netkar_str = f"{net_gelir/1e6:.0f}Mn₺" if net_gelir else "?"
        gelir_str  = f"{top_gelir/1e6:.0f}Mn₺" if top_gelir else "?"
        lines.append(
            f"{r['ticker']}: Piyasa Değeri={mktcap}, Fiyat=₺{r.get('pnl_pct','?')} K/Z, "
            f"F/K={r['fk']}, PD/DD={r['pd_dd']}, ROE=%{r['roe']}, "
            f"NetMarj=%{r['net_margin']}, GelirBüy=%{r['rev_growth']}, "
            f"EBITDA={ebitda_str}, NetKar={netkar_str}, ToplamGelir={gelir_str}, "
            f"Borç/Özkaynak={r.get('debt_eq','?')}, FundSkor={r['fund_score']}/10, "
            f"Sinyal={r['action']}"
        )
    return "\n".join(lines)

def _fmt_ms(ms: dict) -> str:
    rows = ms.get("rows", [])
    lines = []
    for r in rows:
        lines.append(
            f"{r['ticker']}: Fiyat=₺{r['price']}, Trend={r['trend']}, Yapı={r['structure']}, "
            f"RSI={r['rsi']}, MACD={'Boğa' if r.get('macd_bull') else 'Ayı'}, "
            f"HaftalıkBias={r['weekly_bias']}, R:R=1:{r.get('rr','?')}, "
            f"SL=₺{r.get('sl','?')}, TP1=₺{r.get('tp1','?')}, TP2=₺{r.get('tp2','?')}, "
            f"AISkor={r['ai_score']}, Sinyal={r['action']}"
        )
    return "\n".join(lines)

def _fmt_bw(bw: dict) -> str:
    rows = bw.get("rows", [])
    lines = []
    for r in rows:
        lines.append(
            f"{r['ticker']}: Ağırlık=%{r['weight']}, K/Z=%{r['pnl_pct']}, "
            f"Yıllık Volatilite=%{r.get('vol_annual','?')}, Beta={r.get('beta','?')}, "
            f"Max Drawdown=%{r.get('max_drawdown','?')}, Sharpe={r.get('sharpe','?')}"
        )
    lines.append(
        f"\nPortföy: Volatilite=%{bw.get('port_vol','?')}, "
        f"Konsantrasyon={bw.get('concentration','?')}, "
        f"HHI={bw.get('hhi','?')}, "
        f"Sektör Sayısı={bw.get('n_sectors','?')}"
    )
    return "\n".join(lines)

def _fmt_ren(ren: dict) -> str:
    rows = ren.get("rows", [])
    lines = []
    for r in rows:
        lines.append(
            f"{r['ticker']}: Değer={r['val_score']}/25, Kalite={r['qual_score']}/25, "
            f"Momentum={r['mom_score']}/25, Büyüme={r['grow_score']}/25, "
            f"Kompozit={r['composite']}/10, Sinyal={r['action']}"
        )
    return "\n".join(lines)

def _fmt_jp(jp: dict) -> str:
    rows = jp.get("rows", [])
    lines = []
    for r in rows:
        lines.append(
            f"{r['ticker']}: EPS=₺{r.get('eps','?')}, F/K={r.get('fk','?')}, "
            f"İleride F/K={r.get('fk_fwd','?')}, KarBüy=%{r.get('kar_buyume','?')}, "
            f"GelirBüy=%{r.get('rev_growth','?')}, RSI={r.get('rsi','?')}, Sinyal={r.get('action','?')}"
        )
    return "\n".join(lines)

def _fmt_blk(blk: dict) -> str:
    rows = blk.get("rows", [])
    lines = []
    for r in rows:
        lines.append(
            f"{r['ticker']}: Değer=₺{r.get('value',0):,.0f}, "
            f"TemettuVerimi=%{r.get('yield_pct',0)}, "
            f"YıllıkGelir=₺{r.get('annual_income',0):,.0f}"
        )
    lines.append(f"Toplam yıllık temettü geliri: ₺{blk.get('total_income',0):,.0f}, Port. Verimi=%{blk.get('port_yield',0)}")
    return "\n".join(lines)

def _fmt_cit(cit: dict) -> str:
    rows = cit.get("rows", [])
    lines = []
    for r in rows:
        lines.append(
            f"Sektör: {r['sector']}, Hisseler: {', '.join(r['tickers'])}, "
            f"Ağırlık=%{r['weight']:.1f}, OrtSkor={r['avg_score']}/10"
        )
    lines.append(f"HHI={cit.get('hhi','?')}, Konsantrasyon={cit.get('concentration','?')}, Sektör Sayısı={cit.get('n_sectors','?')}")
    return "\n".join(lines)


# ─── Ana Giriş Noktası ───────────────────────────────────────────────────────

def _sync_compute(holdings: list[dict]) -> dict:
    """Blocking veri toplama + hesaplamalar — thread'de çalışır."""
    raw = fetch_portfolio_data(holdings)
    return {
        "raw":               raw,
        "gs_fundamental":    calc_gs_fundamental(raw),
        "ms_technical":      calc_ms_technical(raw),
        "bridgewater_risk":  calc_bridgewater_risk(raw),
        "blackrock_dividend":calc_blackrock_dividend(raw),
        "citadel_sector":    calc_citadel_sector(raw),
        "renaissance_quant": calc_renaissance_quant(raw),
        "jpmorgan_earnings": calc_jpmorgan_earnings(raw),
    }


async def full_portfolio_analysis(holdings: list[dict]) -> dict:
    """Tüm portföy analizini yap ve döndür."""
    loop = asyncio.get_event_loop()

    # 1+2. Blocking veri & hesaplama → ayrı thread
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=1) as ex:
        computed = await loop.run_in_executor(ex, _sync_compute, holdings)

    return computed


# ─── Equity Research Raporu ───────────────────────────────────────────────────

async def generate_equity_research(ticker: str) -> dict:
    """
    Template tabanlı Equity Research raporu — sıfır API maliyeti.
    Mevcut analyze_stock() verisini profesyonel rapor formatına dönüştürür.
    """
    from concurrent.futures import ThreadPoolExecutor
    loop = asyncio.get_event_loop()

    with ThreadPoolExecutor(max_workers=1) as ex:
        data = await loop.run_in_executor(ex, analyze_stock, ticker)

    if not data or data.get("error"):
        return {"error": data.get("error") if data else "Veri alınamadı"}

    fund      = data.get("fundamentals") or {}
    tf1d      = data.get("tf_1d") or {}
    price     = data.get("price", 0)
    action    = data.get("ai_action", "")
    score     = data.get("ai_score", 0)
    fib       = tf1d.get("fibonacci") or {}
    news      = data.get("news") or {}
    insider   = data.get("insider") or {}
    bull_obs  = tf1d.get("bull_obs") or []
    bear_obs  = tf1d.get("bear_obs") or []

    # ── Fundamentals helpers ──────────────────────────────────────────
    def fv(key, suffix="", prefix=""):
        v = fund.get(key)
        if v is None or str(v) in ("None", "N/A", "nan"):
            return "Veri yok"
        return f"{prefix}{v}{suffix}"

    sektor      = fund.get("sektor") or "Bilinmiyor"
    endustri    = fund.get("endustri") or "Bilinmiyor"
    piyasa_deg  = fv("piyasa_degeri")
    fund_verdict = data.get("fund_verdict") or ""

    # ── Technical ────────────────────────────────────────────────────
    trend            = tf1d.get("trend") or "—"
    market_structure = tf1d.get("market_structure") or "—"
    rsi              = tf1d.get("rsi")
    ema20  = tf1d.get("ema20")
    ema50  = tf1d.get("ema50")
    ema200 = tf1d.get("ema200")
    supports    = tf1d.get("supports") or []
    resistances = tf1d.get("resistances") or []
    sl       = tf1d.get("sl") or 0
    tp1      = tf1d.get("tp1") or 0
    tp2      = tf1d.get("tp2") or 0
    rr       = tf1d.get("rr") or 0
    macd     = tf1d.get("macd_signal") or {}
    weekly_bias    = data.get("weekly_bias") or "—"
    long_pct       = data.get("long_pct") or 50
    short_pct      = data.get("short_pct") or 50
    market_strength = data.get("market_strength") or 0
    rel_vol        = data.get("rel_vol") or 1.0
    last_bar       = data.get("last_bar_date") or ""

    # ── Derived values ────────────────────────────────────────────────
    target = tp2 or tp1
    if target and price:
        pot = round((target - price) / price * 100, 1)
        target_str = f"₺{target} ({'+' if pot >= 0 else ''}{pot}%)"
    else:
        target_str = "Hesaplanamadı"

    structure_map = {"YUKSELIS": "Yükseliş (HH+HL)", "DUSUS": "Düşüş (LH+LL)", "YATAY": "Yatay Konsolidasyon"}
    structure_str = structure_map.get(market_structure, market_structure)
    trend_icon = "🐂" if trend == "BOĞA" else "🐻"

    if rsi:
        if rsi > 70:   rsi_comment = f"**{rsi:.1f}** — Aşırı alım, dikkat"
        elif rsi < 30: rsi_comment = f"**{rsi:.1f}** — Aşırı satım, fırsat olabilir"
        elif rsi > 55: rsi_comment = f"**{rsi:.1f}** — Yükseliş momentum güçlü"
        elif rsi < 45: rsi_comment = f"**{rsi:.1f}** — Düşüş baskısı mevcut"
        else:          rsi_comment = f"**{rsi:.1f}** — Nötr bölge"
    else:
        rsi_comment = "Veri yok"

    if score >= 7.5:   rating_full, risk_level = "GÜÇLÜ AL ⭐⭐⭐⭐⭐", "Orta"
    elif score >= 6:   rating_full, risk_level = "AL ⭐⭐⭐⭐", "Orta"
    elif score >= 4.5: rating_full, risk_level = "İZLE ⭐⭐⭐", "Orta-Yüksek"
    elif score >= 3:   rating_full, risk_level = "ZAYIF ⭐⭐", "Yüksek"
    else:              rating_full, risk_level = "SAT ⭐", "Çok Yüksek"

    sup_str = " | ".join([f"₺{s}" for s in supports[:3]]) or "Belirsiz"
    res_str = " | ".join([f"₺{r}" for r in resistances[:3]]) or "Belirsiz"

    news_score   = news.get("sentiment_score")
    news_label   = news.get("label") or ""
    news_drivers = news.get("top_drivers") or []
    news_count   = news.get("article_count") or 0
    insider_signal = insider.get("overall_signal") or ""

    now_str = pd.Timestamp.now().strftime("%d/%m/%Y")

    # ── Build report ──────────────────────────────────────────────────
    L = []
    a = L.append

    a(f"## 📋 {ticker} — Equity Research Raporu")
    a(f"*{now_str} | Son Kapanış: {last_bar} | ₺{price}*")
    a(""); a("---"); a("")

    # Rating
    a("### ⭐ Rating & Hedef Fiyat")
    a(f"- **Rating:** {rating_full}")
    a(f"- **AI Puanı:** {score}/10")
    a(f"- **Mevcut Fiyat:** ₺{price}")
    a(f"- **12 Aylık Hedef:** {target_str}")
    a(f"- **Zarar Kes:** {'₺' + str(sl) if sl else 'Hesaplanamadı'}")
    a(f"- **Risk Seviyesi:** {risk_level}")
    if rr: a(f"- **Risk/Ödül:** 1:{rr}")
    a(""); a("---"); a("")

    # Executive Summary
    a("### 📌 Yönetici Özeti")
    exec_lines = [
        f"{ticker} hissesi {sektor} sektöründe faaliyet göstermekte olup analiz skoru **{score}/10** ile **{action}** önerisi almaktadır.",
        f"Teknik yapı {trend_icon} {structure_str} piyasa yapısını göstermekte, haftalık bias **{weekly_bias}** yönünde seyretmektedir.",
    ]
    if news_score:
        exec_lines.append(
            f"Haber duygu skoru **{news_score}/10** ({news_label}) ile "
            f"{'olumlu' if news_score >= 6 else 'olumsuz'} bir medya ortamı mevcuttur."
        )
    L.extend(exec_lines)
    a(""); a("---"); a("")

    # Company Profile
    a("### 🏢 Şirket Profili")
    a(f"- **Sektör:** {sektor}")
    a(f"- **Endüstri:** {endustri}")
    a(f"- **Piyasa Değeri:** {piyasa_deg}")
    if fund_verdict: a(f"- **Temel Değerlendirme:** {fund_verdict}")
    a(""); a("---"); a("")

    # Valuation table
    a("### 📊 Değerleme Analizi")
    a("")
    a("| Metrik | Değer |")
    a("|--------|-------|")
    for key, lbl in [
        ("fk","F/K"), ("pd_dd","PD/DD"), ("ev_favok","EV/FAVÖK"),
        ("roe","ROE"), ("roa","ROA"), ("net_kar_marji","Net Kâr Marjı"),
        ("brut_kar_marji","Brüt Kâr Marjı"), ("faaliyet_marji","Faaliyet Marjı"),
        ("gelir_buyume","Gelir Büyümesi"), ("kar_buyume","Kâr Büyümesi"),
        ("borc_ozkaynak","Borç/Özkaynak"), ("cari_oran","Cari Oran"),
        ("temttu_verimi","Temettü Verimi"),
    ]:
        sfx = "x" if key in ("fk","pd_dd","ev_favok","cari_oran") else "%"
        a(f"| {lbl} | {fv(key, sfx)} |")
    a(""); a("---"); a("")

    # Investment Thesis
    a("### 💡 Yatırım Tezi")
    a("")
    a("**Boğa Senaryosu (Bull Case):**")
    bulls = []
    if trend == "BOĞA":
        bulls.append(f"Güçlü yükseliş trendi: {structure_str} yapısı sürmekte")
    if long_pct > 55:
        bulls.append(f"Piyasa katılımcılarının %{long_pct}'i LONG — güçlü alıcı baskısı")
    if market_strength > 60:
        bulls.append(f"Market gücü %{market_strength} ile güçlü momentum")
    if bull_obs:
        ob = bull_obs[0]
        bulls.append(f"₺{ob['low']}–₺{ob['high']} güçlü talep bölgesi (OB güç: %{ob['strength']})")
    if news_score and news_score >= 6 and news_drivers:
        bulls.append(f"Pozitif haber duygusu: {news_drivers[0]}")
    if not bulls:
        bulls.append("Teknik ve temel veriler incelenmekte, net bir boğa katalizörü henüz oluşmadı")
    for i, b in enumerate(bulls, 1): a(f"{i}. {b}")
    a("")
    a("**Ayı Senaryosu (Bear Case):**")
    bears = []
    if trend != "BOĞA":
        bears.append(f"Düşüş trendi baskısı: {structure_str}")
    if short_pct > 50:
        bears.append(f"Piyasa katılımcılarının %{short_pct}'i SHORT — satıcı baskısı")
    if rsi and rsi > 70:
        bears.append(f"RSI {rsi:.1f} aşırı alım bölgesinde — düzeltme riski")
    if bear_obs:
        ob = bear_obs[0]
        bears.append(f"₺{ob['low']}–₺{ob['high']} arz bölgesi direnci")
    if news_score and news_score < 4:
        bears.append(f"Negatif haber akışı ({news_score}/10) — kısa vadeli baskı")
    bears.append("BIST geneli makro ve kur volatilitesi")
    for i, b in enumerate(bears, 1): a(f"{i}. {b}")
    a(""); a("---"); a("")

    # Catalysts
    a("### ⚡ Katalizörler")
    a("")
    a("**Kısa Vadeli (1-3 ay):**")
    if macd.get("bullish"):
        a(f"- MACD {macd.get('type','')} sinyali — yükseliş momentumu")
    if news_drivers:
        for d in news_drivers[:2]: a(f"- {d}")
    if insider_signal:
        a(f"- Kurumsal hareketler: {insider_signal}")
    if not macd.get("bullish") and not news_drivers and not insider_signal:
        a("- Belirgin kısa vadeli katalizör henüz oluşmadı")
    a("")
    a("**Uzun Vadeli (6-18 ay):**")
    gbuy = fund.get("gelir_buyume")
    if gbuy and str(gbuy) not in ("None", "N/A", "nan"):
        a(f"- Gelir büyümesi trendi: %{gbuy}")
    tv = fv("temttu_verimi", "%")
    if tv != "Veri yok": a(f"- Temettü verimi: {tv}")
    a("- Türkiye ekonomisi büyüme potansiyeli ve sektörel dinamikler")
    a(""); a("---"); a("")

    # Technical Overview
    a("### 📈 Teknik Görünüm")
    a("")
    a(f"- **Trend:** {trend_icon} {trend} | {structure_str}")
    a(f"- **RSI (14):** {rsi_comment}")
    a(f"- **Haftalık Bias:** {weekly_bias}")
    a(f"- **Göreceli Hacim:** {rel_vol}x ({'Yüksek' if rel_vol > 1.5 else 'Düşük' if rel_vol < 0.7 else 'Normal'})")
    if ema20:  a(f"- **EMA 20:** ₺{ema20} ({'↑ üstünde' if price > ema20 else '↓ altında'})")
    if ema50:  a(f"- **EMA 50:** ₺{ema50} ({'↑ üstünde' if price > ema50 else '↓ altında'})")
    if ema200: a(f"- **EMA 200:** ₺{ema200} ({'↑ üstünde' if price > ema200 else '↓ altında'})")
    a(f"- **Destek:** {sup_str}")
    a(f"- **Direnç:** {res_str}")
    if tp1: a(f"- **Hedef 1:** ₺{tp1}")
    if tp2: a(f"- **Hedef 2:** ₺{tp2}")
    if sl:  a(f"- **Zarar Kes:** ₺{sl}")
    fib_nearest = fib.get("nearest_level")
    fib_np      = fib.get("nearest_price")
    if fib_nearest: a(f"- **Fibonacci:** En yakın %{fib_nearest} @ ₺{fib_np}")
    a("")
    if bull_obs or bear_obs:
        a("**Order Block Bölgeleri:**")
        for ob in bull_obs[:2]:
            tested = " ⚡ Test ediliyor" if ob.get("tested") else ""
            a(f"- 🟩 Talep ₺{ob['low']}–₺{ob['high']} | Güç: %{ob['strength']} | {ob['date']}{tested}")
        for ob in bear_obs[:2]:
            tested = " ⚡ Test ediliyor" if ob.get("tested") else ""
            a(f"- 🟥 Arz ₺{ob['low']}–₺{ob['high']} | Güç: %{ob['strength']} | {ob['date']}{tested}")
        a("")
    a("---"); a("")

    # News
    a("### 📰 Haber & Duygu")
    if news_score:
        a(f"- **Duygu Skoru:** {news_score}/10 — {news_label} ({news_count} haber)")
        if news_drivers:
            a("- **Temel Sürücüler:**")
            for d in news_drivers: a(f"  - {d}")
    else:
        a("- Haber verisi mevcut değil")
    a(""); a("---"); a("")

    # Risks
    a("### ⚠️ Riskler")
    risks = []
    try:
        boz_v = fund.get("borc_ozkaynak")
        if boz_v and float(str(boz_v).replace(",", ".")) > 100:
            risks.append(f"Yüksek kaldıraç: Borç/Özkaynak %{boz_v}")
    except Exception:
        pass
    if rsi and rsi > 65:
        risks.append(f"Teknik aşırı alım: RSI {rsi:.1f}")
    if weekly_bias == "Düşüş":
        risks.append("Haftalık negatif bias — düşüş baskısı devam edebilir")
    if news_score and news_score < 4:
        risks.append(f"Negatif medya ortamı: {news_score}/10")
    risks.append("BIST geneli makro riskler (kur, enflasyon, faiz)")
    risks.append("Şirkete özgü operasyonel riskler")
    for i, r in enumerate(risks[:5], 1): a(f"{i}. {r}")
    a(""); a("---"); a("")

    # Conclusion
    a("### ✅ Sonuç & Öneri")
    a("")
    conclusion = (
        f"**{ticker}** için görüşümüz **{action}** yönünde olup AI analiz skoru **{score}/10**'dur. "
    )
    if target: conclusion += f"12 aylık hedef fiyatımız **{target_str}** seviyesindedir. "
    if sl:     conclusion += f"Zarar kes seviyesi ₺{sl} olarak belirlenmiştir. "
    if trend == "BOĞA" and score >= 6:
        conclusion += "Teknik görünüm olumlu, güçlü destek bölgeleri mevcut. Pozisyon açmadan önce risk profilinizi değerlendirin."
    elif score < 4.5:
        conclusion += "Mevcut görünüm olumsuz. Teknik iyileşme sinyali beklenmeden önce izle stratejisi önerilir."
    else:
        conclusion += "Orta vadeli senaryo için teknik doğrulama beklenmesi tavsiye edilir."
    a(conclusion)
    a("")
    a("---")
    a("*Bu rapor CHARTIST AI tarafından otomatik üretilmiştir. Yatırım tavsiyesi niteliği taşımaz.*")

    return {
        "ticker": ticker,
        "price":  price,
        "report": "\n".join(L),
        "action": action,
        "score":  score,
    }
