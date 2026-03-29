"""
Temel Tarayıcı (Fundamental Screener)
Hafif veri çekimi — sadece yfinance info, tam teknik analiz yok.
Mevcut analyze_stock cache'i öncelikli kullanır.
"""
import yfinance as yf
import time

from stocks import CATEGORIES
try:
    from analyzer import _yf_session as _session
except ImportError:
    _session = None

_fund_cache: dict = {}
_fund_time: dict = {}
_FUND_TTL = 21600  # 6 saat


def _fetch_fund(ticker: str, main_cache: dict | None = None) -> dict | None:
    """Fundamental metrikler. Ana cache varsa oradan alır, yoksa hafif fetch yapar."""

    # 1. Ana uygulama cache'i: analyze_stock sonucu zaten var mı?
    if main_cache and ticker in main_cache:
        cached = main_cache[ticker]
        if cached and not cached.get("error"):
            fund = cached.get("fund") or {}
            return {
                "ticker": ticker,
                "price": cached.get("price"),
                "ai_action": cached.get("ai_action"),
                "ai_score": cached.get("ai_score"),
                "trend": cached.get("trend"),
                # Kârlılık
                "roe":            fund.get("roe"),
                "roa":            fund.get("roa"),
                "faaliyet_marji": fund.get("faaliyet_marji"),
                "brut_kar_marji": fund.get("brut_kar_marji"),
                "net_kar_marji":  fund.get("net_kar_marji"),
                # Büyüme
                "gelir_buyume":   fund.get("gelir_buyume"),
                "kar_buyume":     fund.get("kar_buyume"),
                # Değerleme
                "fk":             fund.get("fk"),
                "ileri_fk":       fund.get("fk_forward"),
                "pd_dd":          fund.get("pd_dd"),
                "ev_favok":       fund.get("ev_favok"),
                # Finansal sağlık
                "borc_ozkaynak":  fund.get("borc_ozkaynak"),
                "cari_oran":      fund.get("cari_oran"),
                "hizli_oran":     fund.get("hizli_oran"),
                "net_borc_favok": fund.get("net_borc_favok"),
                # Temettü
                "temttu_verimi":  fund.get("temttu_verimi"),
                "sektor":         fund.get("sektor", ""),
            }

    # 2. Kendi hafif cache'i
    if ticker in _fund_cache and time.time() - _fund_time.get(ticker, 0) < _FUND_TTL:
        return _fund_cache[ticker]

    # 3. Yfinance hafif çekimi
    try:
        info = yf.Ticker(f"{ticker}.IS", session=_session).info or {}
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        if not price:
            return None

        def v(key):
            val = info.get(key)
            if val is None:
                return None
            try:
                f = float(val)
                return None if f != f else f  # NaN check
            except Exception:
                return None

        def pct(key):
            val = v(key)
            return round(val * 100, 2) if val is not None else None

        td = v("totalDebt") or 0
        tc = v("totalCash") or 0
        eb = v("ebitda")
        net_borc_favok = None
        if eb and eb != 0:
            raw = (td - tc) / abs(eb)
            net_borc_favok = round(raw, 2) if raw > -50 else None  # skip extreme net-cash

        result = {
            "ticker":         ticker,
            "price":          price,
            "ai_action":      None,
            "ai_score":       None,
            "trend":          None,
            "roe":            pct("returnOnEquity"),
            "roa":            pct("returnOnAssets"),
            "faaliyet_marji": pct("operatingMargins"),
            "brut_kar_marji": pct("grossMargins"),
            "net_kar_marji":  pct("profitMargins"),
            "gelir_buyume":   pct("revenueGrowth"),
            "kar_buyume":     pct("earningsGrowth"),
            "fk":             v("trailingPE"),
            "ileri_fk":       v("forwardPE"),
            "pd_dd":          v("priceToBook"),
            "ev_favok":       v("enterpriseToEbitda"),
            "borc_ozkaynak":  v("debtToEquity"),
            "cari_oran":      v("currentRatio"),
            "hizli_oran":     v("quickRatio"),
            "net_borc_favok": net_borc_favok,
            "temttu_verimi":  pct("dividendYield"),
            "sektor":         info.get("sector", ""),
        }
        _fund_cache[ticker] = result
        _fund_time[ticker] = time.time()
        return result
    except Exception:
        return None


def run_screen(category: str, filters: list[dict], main_cache: dict | None = None) -> list[dict]:
    tickers = CATEGORIES.get(category.upper(), CATEGORIES.get("BIST30", []))
    results = []
    for t in tickers:
        m = _fetch_fund(t, main_cache)
        if not m:
            continue
        if _passes(m, filters):
            results.append(m)
    results.sort(key=lambda x: (x.get("roe") or -999), reverse=True)
    return results


def _passes(m: dict, filters: list[dict]) -> bool:
    for f in filters:
        field = f.get("field")
        min_v = f.get("min")
        max_v = f.get("max")
        val = m.get(field)
        if val is None:
            continue  # veri yoksa reddetme
        if min_v is not None and val < min_v:
            return False
        if max_v is not None and val > max_v:
            return False
    return True
