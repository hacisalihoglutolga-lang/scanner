import { useState, useEffect, useCallback, useRef, useMemo } from 'react'
import StockCard from './components/StockCard'
import DetailPage from './components/DetailPage'
import PortfolioPage from './components/PortfolioPage'
import ScreenerPage from './components/ScreenerPage'
import SignalsPage from './components/SignalsPage'
import BacktestPage from './components/BacktestPage'
import LoginPage from './components/LoginPage'
import UsersPage from './components/UsersPage'
import './App.css'

const CATS = [
  { key: 'BIST30',  label: 'BIST 30' },
  { key: 'BIST100', label: 'BIST 100' },
  { key: 'TÜMÜ',   label: 'Tüm Hisseler' },
]
const ACTIONS = [
  { key: 'TÜMÜ',     label: 'Tümü',     color: '' },
  { key: 'GÜÇLÜ AL', label: '⬆ Güçlü Al', color: 'amber' },
  { key: 'AL',       label: '↑ Al',      color: 'green' },
  { key: 'İZLE',     label: '◉ İzle',    color: 'blue' },
  { key: 'ZAYIF',    label: '↓ Zayıf',   color: 'orange' },
  { key: 'SAT',      label: '⬇ Sat',     color: 'red' },
]
const INTERVALS = [
  { label: '5 dk',  ms: 300000 },
  { label: '15 dk', ms: 900000 },
  { label: '30 dk', ms: 1800000 },
  { label: 'Manuel',ms: 0 },
]

const ACTION_COLOR = {
  'GÜÇLÜ AL': 'amber',
  'AL':        'green',
  'İZLE':      'blue',
  'ZAYIF':     'orange',
  'SAT':       'red',
}

const ACTION_ORDER = { 'GÜÇLÜ AL': 0, 'AL': 1, '\u0130ZLE': 2, 'ZAYIF': 3, 'SAT': 4 }
const SETUP_ORDER  = { 'KIRILIM': 0, 'DÖNÜŞ': 1, 'STANDART': 2 }

// ── Auth yardımcıları ─────────────────────────────────────────────────────────
function getToken()    { return localStorage.getItem('ths_token') || '' }
function getUsername() { return localStorage.getItem('ths_user')  || '' }
function getIsAdmin()  {
  try {
    const token = getToken()
    if (!token) return false
    const payload = JSON.parse(atob(token.split('.')[1]))
    return !!payload.admin
  } catch { return false }
}

// Tüm API isteklerine otomatik token ekle, 401'de logout
const _origFetch = window.fetch
window.fetch = async (url, opts = {}) => {
  const token = getToken()
  if (token && typeof url === 'string' && url.startsWith('/api/')) {
    opts = { ...opts, headers: { ...opts.headers, Authorization: `Bearer ${token}` } }
  }
  const res = await _origFetch(url, opts)
  if (res.status === 401 && typeof url === 'string' && url.startsWith('/api/') && !url.includes('/api/login')) {
    localStorage.removeItem('ths_token')
    localStorage.removeItem('ths_user')
    window.location.reload()
  }
  return res
}

// ── Favoriler localStorage yardımcıları ──────────────────────────────────────
function loadFavs() {
  try { return new Set(JSON.parse(localStorage.getItem('ths_favs') || '[]')) }
  catch { return new Set() }
}
function saveFavs(set) {
  localStorage.setItem('ths_favs', JSON.stringify([...set]))
}

// ── Browser bildirimi ────────────────────────────────────────────────────────
function requestNotifPerm() {
  if ('Notification' in window && Notification.permission === 'default') {
    Notification.requestPermission()
  }
}
function sendNotif(title, body) {
  if ('Notification' in window && Notification.permission === 'granted') {
    new Notification(title, { body, icon: '/favicon.ico' })
  }
}

// ── CSV Export ───────────────────────────────────────────────────────────────
function exportCSV(stocks) {
  const cols = ['ticker','price','change_pct','ai_action','ai_score','trend',
                'rsi','long_pct','short_pct','sl','tp1','tp2','rr','last_bar_date']
  const header = cols.join(',')
  const rows = stocks.map(s =>
    cols.map(c => {
      const v = s[c]
      if (v === null || v === undefined) return ''
      if (typeof v === 'string' && v.includes(',')) return `"${v}"`
      return v
    }).join(',')
  )
  const csv = [header, ...rows].join('\n')
  const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `bist-tarama-${new Date().toISOString().slice(0,10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

// ── Auth wrapper — login kontrolünü hook'lardan önce ayır ────────────────────
export default function AppRoot() {
  const [token, setToken]       = useState(getToken)
  const [username, setUsername] = useState(getUsername)

  const handleLogin = (t, u) => { setToken(t); setUsername(u) }
  const handleLogout = () => {
    localStorage.removeItem('ths_token')
    localStorage.removeItem('ths_user')
    setToken(''); setUsername('')
  }

  if (!token) return <LoginPage onLogin={handleLogin} />
  return <App token={token} username={username} isAdmin={getIsAdmin()} onLogout={handleLogout} />
}

function App({ token, username, isAdmin, onLogout }) {
  const [page, setPage]         = useState('scanner')
  const [cat, setCat]           = useState('BIST30')
  const [stocks, setStocks]     = useState([])
  const [loading, setLoading]   = useState(false)
  const [scanning, setScanning] = useState(false)
  const [lastScan, setLastScan] = useState(null)
  const [autoMs, setAutoMs]     = useState(0)
  const [actionF, setActionF]   = useState('TÜMÜ')
  const [filterTf, setFilterTf] = useState('genel')
  const [sortMode, setSortMode] = useState('sinyal')   // 'sinyal' | 'genel' | '4h' | '1d' | '1w' | '1mo'
  const [minScore, setMinScore] = useState(0)
  const [search, setSearch]     = useState('')
  const [pending, setPending]   = useState([])
  const [detail, setDetail]     = useState(null)
  const [searchLoading, setSearchLoading] = useState(false)
  const [allTickers, setAllTickers] = useState([])
  const [showDrop, setShowDrop] = useState(false)
  const [favs, setFavs]         = useState(loadFavs)
  const [showFavsOnly, setShowFavsOnly] = useState(false)
  const timerRef  = useRef(null)
  const epochRef  = useRef(0)
  const prevGucluRef = useRef(new Set())  // bildirim için önceki GÜÇLÜ AL seti
  const screenerCacheRef = useRef(null)

  // Bildirim izni iste
  useEffect(() => { requestNotifPerm() }, [])

  // Load full BIST ticker list once for autocomplete
  useEffect(() => {
    fetch('/api/stocks')
      .then(r => r.json())
      .then(data => {
        if (data.categories) {
          const all = new Set()
          Object.values(data.categories).forEach(arr => arr.forEach(t => all.add(t)))
          setAllTickers([...all].sort())
        }
      })
      .catch(() => {})
  }, [])

  // GÜÇLÜ AL bildirimi — yeni gelen GÜÇLÜ AL sinyallerini bildir
  useEffect(() => {
    const newGuclu = stocks.filter(s => s.ai_action === 'GÜÇLÜ AL').map(s => s.ticker)
    const reallyNew = newGuclu.filter(t => !prevGucluRef.current.has(t))
    if (reallyNew.length > 0) {
      sendNotif(
        '⬆ Güçlü Al Sinyali',
        reallyNew.join(', ') + ' için GÜÇLÜ AL sinyali oluştu'
      )
    }
    prevGucluRef.current = new Set(newGuclu)
  }, [stocks])

  // Favoriler kaydet
  const toggleFav = useCallback((ticker) => {
    setFavs(prev => {
      const next = new Set(prev)
      next.has(ticker) ? next.delete(ticker) : next.add(ticker)
      saveFavs(next)
      return next
    })
  }, [])

  // Herhangi bir hisseyi isimle getir ve detay aç
  const fetchAndShowDetail = useCallback(async (ticker) => {
    const upper = ticker.trim().toUpperCase()
    if (!upper) return

    const inList = stocks.find(s => s.ticker === upper)
    if (inList) { setDetail(inList); return }

    setSearchLoading(true)
    try {
      const res  = await fetch(`/api/stock/${upper}`)
      const data = await res.json()
      if (data && !data.error) setDetail(data)
      else alert(`"${upper}" bulunamadı veya veri çekilemedi.`)
    } catch { alert('Bağlantı hatası') }
    finally { setSearchLoading(false) }
  }, [stocks])

  const doFetch = useCallback(async (c = cat, force = false) => {
    const myEpoch = ++epochRef.current
    setScanning(true)
    if (force) setStocks([])  // Sadece force=true'da kartları temizle
    setLoading(true)
    setPending([])

    const poll = async (isFirst = false) => {
      if (epochRef.current !== myEpoch) return
      try {
        const forceParam = force && isFirst ? '&force=true' : ''
        const res  = await fetch(`/api/scan/stream?category=${encodeURIComponent(c)}&limit=1000${forceParam}`)
        const data = await res.json()
        if (epochRef.current !== myEpoch) return
        if (data.stocks?.length > 0) { setStocks(data.stocks); setLastScan(new Date()) }
        setLoading(false)
        if (data.pending?.length > 0) {
          setPending(data.pending)
          setScanning(true)
          setTimeout(poll, 3000)
        } else {
          setPending([])
          setScanning(false)
        }
      } catch (e) { console.error(e); setScanning(false); setLoading(false) }
    }
    poll(true)
  }, [cat])

  // Manuel mod — sayfa açılışında otomatik tarama yok
  useEffect(() => {
    if (timerRef.current) clearInterval(timerRef.current)
    if (autoMs > 0) timerRef.current = setInterval(() => doFetch(), autoMs)
    return () => clearInterval(timerRef.current)
  }, [autoMs, doFetch])

  // Autocomplete suggestions
  const suggestions = useMemo(() => {
    const q = search.trim().toUpperCase()
    if (!q || q.length < 1) return []

    const loaded = stocks
      .filter(s => s.ticker.includes(q))
      .slice(0, 5)
      .map(s => ({ ticker: s.ticker, loaded: true, action: s.ai_action, score: s.ai_score }))

    const loadedSet = new Set(loaded.map(s => s.ticker))

    const unloaded = allTickers
      .filter(t => t.includes(q) && !loadedSet.has(t))
      .slice(0, 5)
      .map(t => ({ ticker: t, loaded: false }))

    return [...loaded, ...unloaded].slice(0, 8)
  }, [search, stocks, allTickers])

  const handleSearchChange = (e) => {
    setSearch(e.target.value)
    setShowDrop(true)
  }

  const handleSearchKeyDown = (e) => {
    if (e.key === 'Enter' && search.trim()) {
      setShowDrop(false)
      fetchAndShowDetail(search)
    }
    if (e.key === 'Escape') {
      setShowDrop(false)
    }
  }

  const handleSuggestionClick = (ticker) => {
    setSearch('')
    setShowDrop(false)
    fetchAndShowDetail(ticker)
  }

  const TF_ACTION_KEY = {
    genel: 'ai_action', '4h': 'action_4h', '1d': 'action_1d', '1w': 'action_1w', '1mo': 'action_1mo'
  }
  const TF_SCORE_KEY = {
    genel: 'ai_score', '4h': s => s.tf_4h?.score, '1d': s => s.tf_1d?.score,
    '1w': s => s.tf_1w?.score, '1mo': s => s.tf_1mo?.score
  }
  const getAction = (s) => s[TF_ACTION_KEY[filterTf]] ?? s.ai_action
  const getScore  = (s) => {
    const k = TF_SCORE_KEY[filterTf]
    return typeof k === 'function' ? (k(s) ?? s.ai_score) : s[k]
  }

  const SORT_SCORE_FN = {
    genel: s => s.ai_score ?? 0,
    '4h':  s => s.tf_4h?.score ?? 0,
    '1d':  s => s.tf_1d?.score ?? 0,
    '1w':  s => s.tf_1w?.score ?? 0,
    '1mo': s => s.tf_1mo?.score ?? 0,
  }

  const filtered = stocks
    .filter(s => {
      if (showFavsOnly && !favs.has(s.ticker)) return false
      if (actionF !== 'TÜMÜ' && getAction(s) !== actionF) return false
      if (s.ai_score < minScore) return false
      if (search && !s.ticker.toLowerCase().includes(search.toLowerCase())) return false
      return true
    })
    .sort((a, b) => {
      if (sortMode !== 'sinyal') {
        const scoreFn = SORT_SCORE_FN[sortMode] ?? (s => s.ai_score ?? 0)
        return scoreFn(b) - scoreFn(a)
      }
      const oa = ACTION_ORDER[getAction(a)] ?? 5
      const ob = ACTION_ORDER[getAction(b)] ?? 5
      if (oa !== ob) return oa - ob
      const sa = SETUP_ORDER[a.setup_type] ?? 2
      const sb = SETUP_ORDER[b.setup_type] ?? 2
      if (sa !== sb) return sa - sb
      return (getScore(b) ?? 0) - (getScore(a) ?? 0)
    })

  const stats = {
    total:     filtered.length,
    gucluAl:  filtered.filter(s => s.ai_action === 'GÜÇLÜ AL').length,
    al:        filtered.filter(s => s.ai_action === 'AL').length,
    izle:      filtered.filter(s => s.ai_action === 'İZLE').length,
    sat:       filtered.filter(s => s.ai_action === 'SAT').length,
    boga:      filtered.filter(s => s.trend === 'BOĞA').length,
  }

  if (page === 'portfolio') {
    return (
      <>
        {detail && <DetailPage stock={detail} onClose={() => setDetail(null)} />}
        <PortfolioPage onBack={() => setPage('scanner')} onTickerClick={fetchAndShowDetail} />
      </>
    )
  }
  if (page === 'screener') {
    return (
      <>
        {detail && <DetailPage stock={detail} onClose={() => setDetail(null)} />}
        <ScreenerPage onBack={() => setPage('scanner')} onTickerClick={fetchAndShowDetail} cache={screenerCacheRef} />
      </>
    )
  }
  if (page === 'signals') {
    return (
      <>
        {detail && <DetailPage stock={detail} onClose={() => setDetail(null)} />}
        <SignalsPage onBack={() => setPage('scanner')} onTickerClick={fetchAndShowDetail} />
      </>
    )
  }
  if (page === 'backtest') {
    return <BacktestPage onBack={() => setPage('scanner')} />
  }
  if (page === 'users') {
    return <UsersPage onBack={() => setPage('scanner')} token={token} />
  }

  return (
    <div className="app">
      {detail && <DetailPage stock={detail} onClose={() => setDetail(null)} />}

      {/* ── Header ── */}
      <header className="header">
        <div className="hdr-left">
          <div className="logo">
            <span className="logo-icon">◈</span>
            <span className="logo-text">THS</span>
            <span className="logo-sub">AI Terminal</span>
          </div>
          <div className="scan-info">
            {scanning && <span className="dot-pulse"/>}
            {lastScan && !scanning && <span className="last-scan-txt">Son tarama: {lastScan.toLocaleTimeString('tr-TR')}</span>}
            {scanning && <span className="last-scan-txt">Taranıyor…</span>}
          </div>
        </div>

        <div className="hdr-right">
          {/* Endeks seçimi */}
          <div className="ctrl-group">
            <span className="ctrl-label">Endeks</span>
            {CATS.map(c => (
              <button key={c.key}
                className={`pill ${cat === c.key ? 'pill-active' : ''}`}
                onClick={() => setCat(c.key)}
              >{c.label}</button>
            ))}
          </div>

          {/* Zaman dilimi filtresi */}
          <div className="ctrl-group">
            <span className="ctrl-label">Periyot</span>
            {[
              { key: 'genel', label: 'Genel' },
              { key: '4h',    label: '4 Saat' },
              { key: '1d',    label: 'Günlük' },
              { key: '1w',    label: 'Haftalık' },
              { key: '1mo',   label: 'Aylık' },
            ].map(tf => (
              <button key={tf.key}
                className={`pill ${filterTf === tf.key ? 'pill-active' : ''}`}
                onClick={() => setFilterTf(tf.key)}
              >{tf.label}</button>
            ))}
          </div>

          {/* Sıralama */}
          <div className="ctrl-group">
            <span className="ctrl-label">Sırala</span>
            {[
              { key: 'sinyal', label: 'Sinyal' },
              { key: 'genel',  label: 'Genel ↓' },
              { key: '4h',     label: '4S ↓' },
              { key: '1d',     label: 'Gün ↓' },
              { key: '1w',     label: 'Hft ↓' },
              { key: '1mo',    label: 'Aylık ↓' },
            ].map(s => (
              <button key={s.key}
                className={`pill ${sortMode === s.key ? 'pill-active' : ''}`}
                onClick={() => setSortMode(s.key)}
              >{s.label}</button>
            ))}
          </div>

          {/* Sinyal filtresi */}
          <div className="ctrl-group">
            <span className="ctrl-label">Sinyal</span>
            {ACTIONS.map(a => (
              <button key={a.key}
                className={`pill ${actionF === a.key ? `pill-active pill-${a.color}` : ''}`}
                onClick={() => setActionF(a.key)}
              >{a.label}</button>
            ))}
          </div>

          {/* Min skor */}
          <div className="ctrl-group score-ctrl">
            <span className="ctrl-label">Min Skor</span>
            <input type="range" min="0" max="9" step="0.5" value={minScore}
              onChange={e => setMinScore(parseFloat(e.target.value))} />
            <span className="score-val">{minScore}+</span>
          </div>

          {/* Arama */}
          <div className="search-wrap">
            <input
              className="search-inp"
              placeholder="🔍  Hisse ara / analiz et…"
              value={search}
              onChange={handleSearchChange}
              onKeyDown={handleSearchKeyDown}
              onFocus={() => search.trim() && setShowDrop(true)}
              onBlur={() => setTimeout(() => setShowDrop(false), 150)}
            />
            {searchLoading && <span className="search-spin">⟳</span>}
            {showDrop && suggestions.length > 0 && (
              <div className="search-dropdown">
                {suggestions.map(s => (
                  <div
                    key={s.ticker}
                    className="search-sugg"
                    onMouseDown={e => e.preventDefault()}
                    onClick={() => handleSuggestionClick(s.ticker)}
                  >
                    <span className="sugg-ticker">{s.ticker}</span>
                    {s.loaded ? (
                      <>
                        <span className={`sugg-action sugg-${ACTION_COLOR[s.action] || ''}`}>
                          {s.action}
                        </span>
                        <span className="sugg-score">{s.score?.toFixed(1)}</span>
                      </>
                    ) : (
                      <span className="sugg-fetch">analiz et ↗</span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Otomatik tarama */}
          <div className="ctrl-group">
            <span className="ctrl-label">Yenile</span>
            {INTERVALS.map(iv => (
              <button key={iv.ms}
                className={`pill pill-sm ${autoMs === iv.ms ? 'pill-active' : ''}`}
                onClick={() => setAutoMs(iv.ms)}
              >{iv.label}</button>
            ))}
          </div>

          <button className="refresh-btn" onClick={() => doFetch(cat, true)} disabled={scanning}>
            {scanning ? '⟳' : '↺'} Tara
          </button>

          {/* Favoriler filtresi */}
          <button
            className={`fav-filter-btn ${showFavsOnly ? 'fav-filter-active' : ''}`}
            onClick={() => setShowFavsOnly(v => !v)}
            title="Sadece favorileri göster"
          >
            {showFavsOnly ? '★' : '☆'} Favoriler {favs.size > 0 && `(${favs.size})`}
          </button>

          {/* CSV Export */}
          {filtered.length > 0 && (
            <button className="export-btn" onClick={() => exportCSV(filtered)} title="CSV olarak indir">
              ↓ CSV
            </button>
          )}

          <button className="screener-nav-btn" onClick={() => setPage('screener')}>
            ⬡ Tarayıcı
          </button>
          <button className="signals-nav-btn" onClick={() => setPage('signals')}>
            🔔 Sinyaller
          </button>
          <button className="portfolio-nav-btn" onClick={() => setPage('portfolio')}>
            📊 Portföy
          </button>
          <button className="backtest-nav-btn" onClick={() => setPage('backtest')}>
            ⚗ Backtest
          </button>
          {isAdmin && (
            <button className="users-nav-btn" onClick={() => setPage('users')} title="Kullanıcı Yönetimi">
              👥
            </button>
          )}
          <div className="user-info">
            <span className="user-name">{username}</span>
            <button className="logout-btn" onClick={onLogout} title="Çıkış yap">⏻</button>
          </div>
        </div>
      </header>

      {/* ── İstatistik Şeridi ── */}
      <div className="stats-bar">
        <StatBadge label="Toplam"    val={stats.total}   />
        <StatBadge label="Güçlü Al" val={stats.gucluAl} cls="amber" />
        <StatBadge label="Al"        val={stats.al}      cls="green" />
        <StatBadge label="İzle"      val={stats.izle}    cls="blue" />
        <StatBadge label="Sat"       val={stats.sat}     cls="red" />
        <StatBadge label="Boğa Trendi" val={stats.boga} cls="teal" />
        {favs.size > 0 && <StatBadge label="Favoriler" val={favs.size} cls="amber" />}
      </div>

      {/* ── Kartlar ── */}
      <main className="cards-wrap">
        {loading && stocks.length === 0 ? (
          <div className="loading-screen">
            <div className="spinner"/>
            <p>BİST hisseleri analiz ediliyor…</p>
            <p className="load-sub">Yahoo Finance'den veri çekiliyor, lütfen bekleyin…</p>
          </div>
        ) : stocks.length === 0 ? (
          <div className="empty-state">Tarama yapmak için ↺ Tara butonuna basın.</div>
        ) : filtered.length === 0 ? (
          <div className="empty-state">
            {showFavsOnly ? 'Favori hisse bulunamadı.' : 'Kriterlere uyan hisse bulunamadı.'}
          </div>
        ) : (
          <div className="cards-grid">
            {filtered.map(s => (
              <StockCard
                key={s.ticker}
                stock={s}
                onDetail={() => setDetail(s)}
                isFav={favs.has(s.ticker)}
                onToggleFav={() => toggleFav(s.ticker)}
              />
            ))}
          </div>
        )}
      </main>
    </div>
  )
}

function StatBadge({ label, val, cls }) {
  return (
    <div className="stat-badge">
      <span className="sb-label">{label}</span>
      <span className={`sb-val ${cls ? 'sb-'+cls : ''}`}>{val}</span>
    </div>
  )
}
