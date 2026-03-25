"""
BIST Çoklu Kaynak Haber & Duygu Analizi
Kaynaklar: Bloomberg HT, HaberTürk, Sabah, Sözcü, Para Analiz + Yahoo Finance (fallback)
"""

import urllib.request
import xml.etree.ElementTree as ET
import time
import re
import threading
from email.utils import parsedate_to_datetime

# ── RSS Haber Kaynakları (Türkçe) ─────────────────────────────────────────────
TR_SOURCES = [
    ("Bloomberg HT",  "https://www.bloomberght.com/rss"),
    ("HaberTürk",     "https://www.haberturk.com/rss/ekonomi.xml"),
    ("Sabah Ekonomi", "https://www.sabah.com.tr/rss/ekonomi.xml"),
    ("Sözcü",         "https://www.sozcu.com.tr/rss/ekonomi"),
    ("Para Analiz",   "https://www.paraanaliz.com/feed/"),
    ("Milliyet",      "https://www.milliyet.com.tr/rss/rssNew/ekonomiRss.xml"),
    ("AA Ekonomi",    "https://www.aa.com.tr/tr/rss/default?cat=ekonomi"),
    ("Investing TR",  "https://tr.investing.com/rss/news_25.rss"),
    ("Investing TR2", "https://tr.investing.com/rss/news_14.rss"),
]

# ── Feed cache: (ts, articles_list) ───────────────────────────────────────────
_feed_cache: dict = {}
_feed_lock = threading.Lock()
FEED_TTL = 300  # 5 dakika

# ── BIST Ticker → Arama Terimleri ─────────────────────────────────────────────
TICKER_TERMS: dict[str, list[str]] = {
    # Bankacılık
    "GARAN":  ["garanti", "garantibbva", "garanti bbva"],
    "AKBNK":  ["akbank"],
    "ISCTR":  ["iş bankası", "işbankası", "isbank", "iş banka"],
    "YKBNK":  ["yapı kredi", "yapikredi"],
    "HALKB":  ["halkbank", "halk bankası", "halk bank"],
    "VAKBN":  ["vakıfbank", "vakıf bank", "vakıfbankas"],
    "ALBRK":  ["albaraka türk", "albaraka"],
    "QNBFB":  ["qnb finansbank", "finansbank"],
    "ZIRAAT": ["ziraat bankası", "ziraat bank"],
    "DENIZ":  ["denizbank"],
    # Holdingler
    "KCHOL":  ["koç holding", "koç grup", "koç grubu"],
    "SAHOL":  ["sabancı holding", "sabancı grubu", "sabanci"],
    "DOHOL":  ["doğan holding", "doğan grubu", "dogan holding"],
    "AGHOL":  ["anadolu grubu", "anadolu holding"],
    "TKFEN":  ["tekfen holding", "tekfen"],
    "ENKAI":  ["enka inşaat", "enka holding"],
    # Havacılık
    "THYAO":  ["türk hava yolları", "thy", "turkish airlines", "turk hava"],
    "PGSUS":  ["pegasus havacılık", "pegasus hava", "pegasus"],
    "TAVHL":  ["tav havalimanları", "tav airport", "tav havaliman"],
    # Otomotiv
    "FROTO":  ["ford otosan", "ford otomobil"],
    "TOASO":  ["tofaş", "tofas", "fiat tofaş"],
    "OTKAR":  ["otokar"],
    "ASUZU":  ["anadolu isuzu", "isuzu"],
    "TTRAK":  ["türk traktör", "türk trak"],
    "DOAS":   ["doğuş otomotiv", "doğuş otomot"],
    # Enerji & Petrokimya
    "TUPRS":  ["tüpraş", "tupras", "türkiye petrol rafineri"],
    "PETKM":  ["petkim"],
    "SASA":   ["sasa polyester", "sasa polye"],
    "AKSEN":  ["aksa enerji", "aksa energy"],
    "ZOREN":  ["zorlu enerji", "zorlu enerj"],
    "ENJSA":  ["enerjisa", "enerjisa enerji"],
    "AYGAZ":  ["aygaz"],
    "ODAS":   ["odaş elektrik", "odaş enerji"],
    # Demir Çelik & Madencilik
    "EREGL":  ["ereğli demir çelik", "ereğli", "erdemir"],
    "KRDMD":  ["kardemir", "karabük demir"],
    "KOZAL":  ["koza altın", "koza altin"],
    "KOZAA":  ["koza anadolu", "koza maden"],
    "GUBRF":  ["gübre fabrikaları", "gübre fab"],
    # Teknoloji & Telekomünikasyon
    "TCELL":  ["turkcell"],
    "TTKOM":  ["türk telekomunikasyon", "türk telekom", "turk telekom"],
    "LOGO":   ["logo yazılım", "logo software"],
    "NETAS":  ["netaş telekomunikasyon", "netas"],
    "INDES":  ["index bilgisayar", "index grup"],
    "ASELS":  ["aselsan", "aselsan savunma"],
    # Cam & İnşaat Malzemeleri
    "SISE":   ["şişecam", "şişe cam", "sise cam"],
    "TRKCM":  ["trakya cam"],
    "CIMSA":  ["çimsa", "cimsa çimento"],
    "AKCNS":  ["akçansa", "akcansa"],
    "BOLUC":  ["bolu çimento"],
    # Perakende & Tüketim
    "BIMAS":  ["bim mağazalar", "bim market", "bim a.ş"],
    "MGROS":  ["migros ticaret", "migros"],
    "SOKM":   ["şok market", "şok marketler", "sok market"],
    "BIZIM":  ["bizim toptan"],
    "MAVI":   ["mavi giyim", "mavi jeans"],
    "LCWGR":  ["lc waikiki"],
    # Gıda & İçecek
    "CCOLA":  ["coca-cola içecek", "cci", "coca cola içecek"],
    "AEFES":  ["anadolu efes", "efes bira", "efes pilsen"],
    "ULKER":  ["ülker bisküvi", "ülker gıda"],
    "TATGD":  ["tat gıda", "tat gıd"],
    "BANVT":  ["banvit gıda", "banvit"],
    # Emlak & GYO
    "EKGYO":  ["emlak konut gyo", "emlak konut", "toki"],
    "ISGYO":  ["iş gayrimenkul", "iş gyo"],
    "OZRDN":  ["özderici"],
    # Sigorta
    "AGESA":  ["agesa sigorta", "agesa"],
    "AKGRT":  ["aksigorta"],
    "ANSGR":  ["anadolu sigorta", "anadolu hayat"],
    # Diğer
    "BRSAN":  ["borusan", "borusan holding"],
    "VESTEL": ["vestel", "vestel elektronik"],
    "ARCLK":  ["arçelik", "arcelik"],
    "TKFEN":  ["tekfen", "tekfen holding"],
}

# ── Duygu Anahtar Kelimeleri ───────────────────────────────────────────────────
_POS_TR = [
    "artış", "yükseliş", "rekor", "büyüme", "güçlü", "olumlu", "tavan",
    "anlaşma", "büyüdü", "arttı", "kazanç", "ihracat", "başarı", "yükseldi",
    "kâr", "kâr açıkladı", "temettü", "hedef yükseltildi", "alım", "pozitif",
    "yukarı revize", "zirve", "beklenti üstü", "güçlendi", "atılım",
    "sipariş", "ödül", "sözleşme", "ihale kazandı", "yatırım", "genişleme",
    "piyasa lideri", "büyük anlaşma", "ihraç", "işbirliği", "ortaklık",
    "kârlılık", "verimlilik", "üretim artışı", "Fitch", "S&P", "moody",
    # KAP özel
    "kâr payı", "temettü dağıtım", "sermaye artırımı", "bedelsiz",
    "geri alım", "hisse geri", "rüçhan", "halka arz", "ihracat artışı",
    "kapasite artışı", "yeni sözleşme", "uzun vadeli anlaşma",
]
_NEG_TR = [
    "düşüş", "kayıp", "zarar", "endişe", "kriz", "düştü", "azaldı",
    "zayıf", "satış", "taban", "iflas", "baskı", "soruşturma", "düşük",
    "olumsuz", "aşağı revize", "ceza", "dava", "zarar açıkladı",
    "hedef düşürüldü", "uyarı", "risk", "beklenti altı", "geri çekilme",
    "çöküş", "iflasın eşiğinde", "borç", "haciz", "tasfiye", "ek vergi",
    "tazminat", "manipülasyon", "sert düşüş", "piyasa kaybı", "istifa",
    # KAP özel
    "ertelendi", "iptal edildi", "özel durum açıklaması", "idari para cezası",
    "sermaye azaltımı", "iflas erteleme", "konkordato", "tdms", "haciz bildirimi",
]
_POS_EN = [
    "surge", "gain", "rise", "rally", "growth", "profit", "record", "beat",
    "strong", "positive", "upgrade", "outperform", "exceed", "deal",
    "partnership", "expand", "revenue", "dividend", "boosts", "wins",
    "higher", "bullish", "recover", "rebound", "buy", "overweight",
    "breakout", "acquisition", "investment", "contract", "awarded",
]
_NEG_EN = [
    "fall", "drop", "decline", "loss", "risk", "concern", "crisis",
    "weak", "sell", "downgrade", "miss", "below", "pressure", "warning",
    "default", "debt", "lawsuit", "tumble", "plunge", "cut", "bearish",
    "investigation", "fraud", "fine", "penalty", "shutdown", "layoff",
]

_ALL_POS = set(_POS_TR + _POS_EN)
_ALL_NEG = set(_NEG_TR + _NEG_EN)


def _parse_rss_date(date_str: str) -> float:
    """RFC 2822 tarihini timestamp'e çevir."""
    if not date_str:
        return 0.0
    try:
        return parsedate_to_datetime(date_str.strip()).timestamp()
    except Exception:
        pass
    try:
        import datetime
        # ISO format
        return datetime.datetime.fromisoformat(
            date_str.replace("Z", "+00:00")
        ).timestamp()
    except Exception:
        return 0.0


def _fetch_feed(name: str, url: str) -> list[dict]:
    """Tek bir RSS kaynağını çek, önbellekten döndür."""
    with _feed_lock:
        cached = _feed_cache.get(url)
        if cached and time.time() - cached[0] < FEED_TTL:
            return cached[1]

    articles = []
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 (BISTScanner/2.0)"}
        )
        with urllib.request.urlopen(req, timeout=6) as r:
            content = r.read()
        root = ET.fromstring(content)
        for item in root.findall(".//item"):
            title_el   = item.find("title")
            desc_el    = item.find("description")
            date_el    = item.find("pubDate")
            link_el    = item.find("link")
            title = title_el.text.strip() if title_el is not None and title_el.text else ""
            desc  = desc_el.text.strip()  if desc_el  is not None and desc_el.text  else ""
            if not title:
                continue
            articles.append({
                "title":     title,
                "desc":      re.sub(r"<[^>]+>", "", desc)[:200],
                "ts":        _parse_rss_date(date_el.text if date_el is not None else ""),
                "source":    name,
                "url":       link_el.text.strip() if link_el is not None and link_el.text else "",
            })
    except Exception:
        pass

    with _feed_lock:
        _feed_cache[url] = (time.time(), articles)
    return articles


def _score_text(text: str) -> tuple[int, int]:
    """Bir metni pozitif/negatif keyword sayısıyla skorla."""
    tl = text.lower()
    pos = sum(1 for kw in _ALL_POS if kw in tl)
    neg = sum(1 for kw in _ALL_NEG if kw in tl)
    return pos, neg


def _terms_for(ticker: str) -> list[str]:
    """Ticker için arama terimlerini döndür (ticker dahil)."""
    base = TICKER_TERMS.get(ticker.upper(), [])
    return [ticker.lower()] + base


def fetch_news_for_ticker(ticker: str, yf_t_obj=None) -> dict:
    """
    Ticker için çoklu kaynaktan haber çek, duygu skoru hesapla.
    TR RSS kaynakları öncelikli; bulunamazsa Yahoo Finance'e fallback.
    """
    terms = _terms_for(ticker)
    matched: list[dict] = []

    # ── TR RSS Kaynakları (paralel) ───────────────────────────────────────────
    import concurrent.futures
    all_articles: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=9) as ex:
        futures = {ex.submit(_fetch_feed, name, url): name for name, url in TR_SOURCES}
        for fut in concurrent.futures.as_completed(futures, timeout=8):
            try:
                all_articles.extend(fut.result())
            except Exception:
                pass

    # Eşleştir: başlık veya açıklamada şirket adı geçiyor mu?
    seen_titles = set()
    for art in all_articles:
        combined = (art["title"] + " " + art["desc"]).lower()
        if any(term in combined for term in terms):
            key = art["title"][:80]
            if key not in seen_titles:
                seen_titles.add(key)
                matched.append({**art, "lang": "TR"})

    # ── Yahoo Finance Fallback ─────────────────────────────────────────────────
    yf_articles: list[dict] = []
    if yf_t_obj is not None:
        try:
            import datetime as _dt
            news_items = yf_t_obj.news or []
            for item in news_items:
                content  = item.get("content", item)
                title    = content.get("title", item.get("title", ""))
                if not title:
                    continue
                pub_str  = content.get("pubDate", content.get("displayTime", ""))
                ts = 0.0
                if pub_str:
                    try:
                        ts = _dt.datetime.fromisoformat(
                            pub_str.replace("Z", "+00:00")
                        ).timestamp()
                    except Exception:
                        ts = float(item.get("providerPublishTime", 0) or 0)
                prov = content.get("provider", {})
                publisher = prov.get("displayName", "") if isinstance(prov, dict) else ""
                yf_articles.append({
                    "title":  title,
                    "desc":   content.get("summary", "")[:200],
                    "ts":     ts,
                    "source": publisher or "Yahoo Finance",
                    "url":    "",
                    "lang":   "EN",
                })
        except Exception:
            pass

    # TR haberlerde yeterli veri yoksa Yahoo'yu da ekle
    if len(matched) < 3:
        matched.extend(yf_articles)

    if not matched:
        return {}

    # ── Skor Hesapla ─────────────────────────────────────────────────────────
    pos_total = neg_total = 0
    scored: list[dict] = []
    for art in matched:
        pos, neg = _score_text(art["title"] + " " + art.get("desc", ""))
        pos_total += pos
        neg_total += neg
        scored.append({**art, "net": pos - neg})

    total_sig = pos_total + neg_total
    pos_ratio = pos_total / max(total_sig, 1)

    if total_sig == 0:
        sentiment_score = 5.0
    else:
        sentiment_score = round(1.0 + pos_ratio * 9.0, 1)

    if   sentiment_score >= 7.5: label, emoji = "OLUMLU",        "😊"
    elif sentiment_score >= 6.0: label, emoji = "HAFIF OLUMLU",  "🙂"
    elif sentiment_score >= 4.5: label, emoji = "NÖTR",          "😐"
    elif sentiment_score >= 3.0: label, emoji = "KARIŞIK",       "😟"
    else:                        label, emoji = "OLUMSUZ",        "😨"

    # Top 3 etkili başlık
    top3 = sorted(scored, key=lambda x: abs(x["net"]), reverse=True)[:3]
    top_drivers = [{
        "title":     d["title"][:130],
        "publisher": d["source"],
        "direction": "pos" if d["net"] > 0 else ("neg" if d["net"] < 0 else "neu"),
    } for d in top3]

    # Son 8 haber (en yeni önce)
    display = sorted(matched, key=lambda x: x["ts"], reverse=True)[:8]
    headlines = [{
        "title":     n["title"][:130],
        "publisher": n["source"],
        "lang":      n.get("lang", ""),
        "date":      time.strftime("%d.%m", time.localtime(n["ts"])) if n["ts"] else "?",
    } for n in display]

    # Kaynak dağılımı
    tr_count = sum(1 for a in matched if a.get("lang") == "TR")
    en_count = len(matched) - tr_count

    # Tarih aralığı
    all_ts = [a["ts"] for a in matched if a["ts"] > 0]
    oldest = time.strftime("%d.%m.%Y", time.localtime(min(all_ts))) if all_ts else ""
    newest = time.strftime("%d.%m.%Y", time.localtime(max(all_ts))) if all_ts else ""

    # Kaynak listesi
    sources_used = sorted(set(a["source"] for a in matched))

    return {
        "sentiment_score": sentiment_score,
        "label":           label,
        "emoji":           emoji,
        "article_count":   len(matched),
        "tr_count":        tr_count,
        "en_count":        en_count,
        "pos_signals":     pos_total,
        "neg_signals":     neg_total,
        "top_drivers":     top_drivers,
        "headlines":       headlines,
        "sources_used":    sources_used,
        "date_range":      f"{oldest} – {newest}" if oldest else "",
    }
