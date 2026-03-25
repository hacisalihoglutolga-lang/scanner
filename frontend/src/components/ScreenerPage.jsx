import { useState, useCallback, useEffect } from 'react'
import DetailPage from './DetailPage'
import PatternScanner from './PatternScanner'
import './ScreenerPage.css'

// ─── Filtre tanımları ──────────────────────────────────────────────────────
const FILTER_DEFS = [
  // Kârlılık
  { id: 'roe',            group: 'karlilik', label: 'ÖGO (ROE)',         unit: '%',  desc: 'Özkaynak Karlılığı' },
  { id: 'roa',            group: 'karlilik', label: 'ROTA (ROA)',        unit: '%',  desc: 'Aktif Karlılığı' },
  { id: 'faaliyet_marji', group: 'karlilik', label: 'Faaliyet Marjı',   unit: '%',  desc: 'Operating Margin' },
  { id: 'brut_kar_marji', group: 'karlilik', label: 'Brüt Kâr Marjı',  unit: '%',  desc: 'Gross Margin' },
  { id: 'net_kar_marji',  group: 'karlilik', label: 'Net Kâr Marjı',    unit: '%',  desc: 'Net Margin' },
  // Büyüme
  { id: 'gelir_buyume',   group: 'buyume',   label: 'Gelir Büyümesi',   unit: '%',  desc: 'Revenue Growth YoY' },
  { id: 'kar_buyume',     group: 'buyume',   label: 'EPS Büyümesi',     unit: '%',  desc: 'Earnings Growth YoY' },
  // Değerleme
  { id: 'fk',             group: 'deger',    label: 'F/K (P/E)',         unit: 'x',  desc: 'Fiyat / Kazanç' },
  { id: 'ileri_fk',       group: 'deger',    label: 'İleri F/K',        unit: 'x',  desc: 'Forward P/E' },
  { id: 'pd_dd',          group: 'deger',    label: 'PD/DD (P/B)',       unit: 'x',  desc: 'Piyasa / Defter' },
  { id: 'ev_favok',       group: 'deger',    label: 'EV/FAVÖK',         unit: 'x',  desc: 'Enterprise Value / EBITDA' },
  // Finansal Sağlık
  { id: 'borc_ozkaynak',  group: 'saglik',   label: 'Borç/Öz Sermaye', unit: 'x',  desc: 'Debt / Equity' },
  { id: 'cari_oran',      group: 'saglik',   label: 'Cari Oran',        unit: 'x',  desc: 'Current Ratio' },
  { id: 'hizli_oran',     group: 'saglik',   label: 'Hızlı Oran',       unit: 'x',  desc: 'Quick Ratio' },
  { id: 'net_borc_favok', group: 'saglik',   label: 'Net Borç/FAVÖK', unit: 'x',  desc: 'Net Debt / EBITDA' },
  // Temettü
  { id: 'temttu_verimi',  group: 'temettu',  label: 'Temettü Verimi',  unit: '%',  desc: 'Dividend Yield' },
]

const GROUPS = [
  { id: 'karlilik', label: 'Kârlılık' },
  { id: 'buyume',   label: 'Büyüme' },
  { id: 'deger',    label: 'Değerleme' },
  { id: 'saglik',   label: 'Finansal Sağlık' },
  { id: 'temettu',  label: 'Temettü' },
]

// ─── Preset tanımları ──────────────────────────────────────────────────────
const PRESETS = {
  'Yeni Temel': [
    { id: 'roe',            min: 8,   max: null, enabled: true },
    { id: 'roa',            min: 8,   max: null, enabled: true },
    { id: 'faaliyet_marji', min: 10,  max: null, enabled: true },
    { id: 'brut_kar_marji', min: 20,  max: null, enabled: true },
    { id: 'gelir_buyume',   min: 8,   max: null, enabled: true },
    { id: 'kar_buyume',     min: 8,   max: null, enabled: true },
    { id: 'borc_ozkaynak',  min: null,max: 20,   enabled: true },
    { id: 'cari_oran',      min: 1,   max: 10,   enabled: true },
    { id: 'net_borc_favok', min: null,max: 3,    enabled: true },
  ],
  'Değer': [
    { id: 'fk',     min: null, max: 15,  enabled: true },
    { id: 'pd_dd',  min: null, max: 1.5, enabled: true },
    { id: 'ev_favok',min: null,max: 10,  enabled: true },
    { id: 'roe',    min: 10,   max: null,enabled: true },
  ],
  'Büyüme': [
    { id: 'gelir_buyume',   min: 20,  max: null, enabled: true },
    { id: 'kar_buyume',     min: 20,  max: null, enabled: true },
    { id: 'faaliyet_marji', min: 10,  max: null, enabled: true },
    { id: 'cari_oran',      min: 1,   max: null, enabled: true },
  ],
  'Temettü': [
    { id: 'temttu_verimi', min: 3,    max: null, enabled: true },
    { id: 'fk',            min: null, max: 20,   enabled: true },
    { id: 'cari_oran',     min: 1,    max: null, enabled: true },
    { id: 'borc_ozkaynak', min: null, max: 50,   enabled: true },
  ],
}

// ─── Başlangıç filtre durumu ───────────────────────────────────────────────
function buildState(presetFilters) {
  const state = {}
  FILTER_DEFS.forEach(d => {
    state[d.id] = { min: null, max: null, enabled: false }
  })
  presetFilters.forEach(p => {
    if (state[p.id] !== undefined) {
      state[p.id] = { min: p.min, max: p.max, enabled: p.enabled }
    }
  })
  return state
}

// ─── Tablo sütunları ───────────────────────────────────────────────────────
const COLS = [
  { key: 'ticker',         label: 'Hisse',          fmt: v => v,                       cls: '' },
  { key: 'price',          label: 'Fiyat',          fmt: v => v != null ? `${v} ₺` : '—', cls: 'num' },
  { key: 'roe',            label: 'ROE %',          fmt: fmtPct,                        cls: 'num', hi: 'good' },
  { key: 'faaliyet_marji', label: 'Faal.Mrj%',      fmt: fmtPct,                        cls: 'num', hi: 'good' },
  { key: 'gelir_buyume',   label: 'Gel.Büy%',       fmt: fmtPct,                        cls: 'num', hi: 'good' },
  { key: 'kar_buyume',     label: 'EPS Büy%',       fmt: fmtPct,                        cls: 'num', hi: 'good' },
  { key: 'borc_ozkaynak',  label: 'D/E',            fmt: fmtNum,                        cls: 'num', hi: 'bad' },
  { key: 'cari_oran',      label: 'Cari',           fmt: fmtNum,                        cls: 'num', hi: 'good' },
  { key: 'fk',             label: 'F/K',            fmt: fmtNum,                        cls: 'num', hi: 'neutral' },
  { key: 'ai_score',       label: 'AI Skor',        fmt: v => v != null ? v.toFixed(1) : '—', cls: 'num', hi: 'good' },
  { key: 'ai_action',      label: 'Sinyal',         fmt: v => v || '—',                 cls: 'action' },
]

function fmtPct(v)  { return v != null ? `${v > 0 ? '+' : ''}${v.toFixed(1)}` : '—' }
function fmtNum(v)  { return v != null ? v.toFixed(2) : '—' }

function cellColor(col, val) {
  if (val == null) return ''
  if (col.hi === 'good') {
    if (val >= 20) return 'sc-green'
    if (val >= 8)  return 'sc-lime'
    if (val < 0)   return 'sc-red'
    return ''
  }
  if (col.hi === 'bad') {
    if (val <= 20) return 'sc-green'
    if (val <= 50) return 'sc-lime'
    if (val > 100) return 'sc-red'
    return ''
  }
  return ''
}

const ACTION_CLS = {
  'GÜÇLÜ AL': 'sa-amber',
  'AL': 'sa-green',
  'İZLE': 'sa-blue',
  'ZAYIF': 'sa-orange',
  'SAT': 'sa-red',
}

// ─── Ana Bileşen ───────────────────────────────────────────────────────────
export default function ScreenerPage({ onBack, onTickerClick, cache }) {
  const c = cache?.current
  const [tab, setTab]             = useState(() => c?.tab ?? 'fundamental')
  const [filters, setFilters]     = useState(() => c?.filters ?? buildState(PRESETS['Yeni Temel']))
  const [activePreset, setActive] = useState(() => c?.activePreset ?? 'Yeni Temel')
  const [category, setCategory]   = useState(() => c?.category ?? 'BIST100')
  const [results, setResults]     = useState(() => c?.results ?? null)
  const [loading, setLoading]     = useState(false)
  const [sortBy, setSortBy]       = useState(() => c?.sortBy ?? 'roe')
  const [sortDir, setSortDir]     = useState(() => c?.sortDir ?? 'desc')
  const [detail, setDetail]       = useState(null)

  // cache'e kaydet
  useEffect(() => {
    if (cache) cache.current = { tab, filters, activePreset, category, results, sortBy, sortDir }
  })

  const applyPreset = (name) => {
    setActive(name)
    setResults(null)
    setFilters(buildState(PRESETS[name]))
  }

  const toggleFilter = (id) => {
    setFilters(f => ({ ...f, [id]: { ...f[id], enabled: !f[id].enabled } }))
  }

  const setMin = (id, val) => {
    setFilters(f => ({ ...f, [id]: { ...f[id], min: val === '' ? null : Number(val) } }))
  }

  const setMax = (id, val) => {
    setFilters(f => ({ ...f, [id]: { ...f[id], max: val === '' ? null : Number(val) } }))
  }

  const doScreen = useCallback(async () => {
    const activeFilters = Object.entries(filters)
      .filter(([, v]) => v.enabled)
      .map(([id, v]) => ({ field: id, min: v.min, max: v.max }))
    setLoading(true)
    setResults(null)
    try {
      const res = await fetch('/api/screen', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ category, filters: activeFilters }),
      })
      const data = await res.json()
      setResults(data.stocks || [])
    } catch (e) { console.error(e) }
    finally { setLoading(false) }
  }, [filters, category])

  const sorted = results ? [...results].sort((a, b) => {
    const av = a[sortBy] ?? -Infinity
    const bv = b[sortBy] ?? -Infinity
    return sortDir === 'desc' ? bv - av : av - bv
  }) : []

  const handleSort = (key) => {
    if (sortBy === key) setSortDir(d => d === 'desc' ? 'asc' : 'desc')
    else { setSortBy(key); setSortDir('desc') }
  }

  const enabledCount = Object.values(filters).filter(f => f.enabled).length

  return (
    <div className="sc-page">
      {detail && <DetailPage stock={detail} onClose={() => setDetail(null)} />}

      {/* ── Header ── */}
      <div className="sc-header">
        <button className="sc-back-btn" onClick={onBack}>← Geri</button>
        <div className="sc-title">
          <span className="sc-title-icon">⬡</span>
          <span className="sc-title-txt">TEMEL TARAYICI</span>
        </div>
        <div className="sc-cat-group">
          {['BIST30','BIST100','TÜMÜ'].map(c => (
            <button key={c}
              className={`sc-cat ${category === c ? 'sc-cat-active' : ''}`}
              onClick={() => setCategory(c)}
            >{c}</button>
          ))}
        </div>
        <button className="sc-run-btn" onClick={doScreen} disabled={loading || enabledCount === 0}>
          {loading ? '⟳ Taranıyor…' : `◉ Tara (${enabledCount} filtre)`}
        </button>
      </div>

      {/* ── Sekmeler ── */}
      <div className="sc-tabs">
        <button className={`sc-tab ${tab === 'fundamental' ? 'sc-tab-active' : ''}`}
          onClick={() => setTab('fundamental')}>
          ◈ Temel Analiz Tarayıcısı
        </button>
        <button className={`sc-tab ${tab === 'pattern' ? 'sc-tab-active' : ''}`}
          onClick={() => setTab('pattern')}>
          ⌁ Formasyon &amp; Elliott Wave Tarayıcısı
        </button>
      </div>

      {tab === 'pattern' && <PatternScanner category={category} onCategoryChange={setCategory} onDetail={setDetail} />}
      {tab === 'pattern' && null /* temel filtreler gizle */}

      {tab === 'fundamental' && <>
      {/* ── Presetler ── */}
      <div className="sc-presets">
        <span className="sc-preset-label">Şablon:</span>
        {Object.keys(PRESETS).map(name => (
          <button key={name}
            className={`sc-preset-btn ${activePreset === name ? 'sc-preset-active' : ''}`}
            onClick={() => applyPreset(name)}
          >{name}</button>
        ))}
        <button className="sc-preset-btn sc-preset-clear"
          onClick={() => { setActive(null); setFilters(buildState([])); setResults(null) }}
        >✕ Temizle</button>
      </div>

      {/* ── Filtreler ── */}
      <div className="sc-filters">
        {GROUPS.map(g => {
          const defs = FILTER_DEFS.filter(d => d.group === g.id)
          return (
            <div key={g.id} className="sc-group">
              <div className="sc-group-title">{g.label}</div>
              {defs.map(d => {
                const f = filters[d.id]
                return (
                  <div key={d.id} className={`sc-filter-row ${f.enabled ? 'sc-filter-on' : ''}`}>
                    <label className="sc-chk-wrap" title={d.desc}>
                      <input type="checkbox" checked={f.enabled} onChange={() => toggleFilter(d.id)} />
                      <span className="sc-filter-lbl">{d.label}</span>
                    </label>
                    <div className="sc-range-inputs">
                      <input
                        type="number" placeholder="min"
                        value={f.min ?? ''} onChange={e => setMin(d.id, e.target.value)}
                        disabled={!f.enabled} className="sc-inp"
                      />
                      <span className="sc-dash">–</span>
                      <input
                        type="number" placeholder="max"
                        value={f.max ?? ''} onChange={e => setMax(d.id, e.target.value)}
                        disabled={!f.enabled} className="sc-inp"
                      />
                      <span className="sc-unit">{d.unit}</span>
                    </div>
                  </div>
                )
              })}
            </div>
          )
        })}
      </div>

      {/* ── Sonuçlar ── */}
      {loading && (
        <div className="sc-loading">
          <div className="sc-spinner"/>
          <span>Hisseler taranıyor… ({category === 'BIST30' ? '~10sn' : category === 'BIST100' ? '~40sn' : '~3dk'})</span>
        </div>
      )}

      {results !== null && !loading && (
        <div className="sc-results">
          <div className="sc-results-hdr">
            <span className="sc-results-count">{sorted.length} hisse bulundu</span>
          </div>
          {sorted.length === 0 ? (
            <div className="sc-empty">Kriterlere uyan hisse bulunamadı. Filtreleri gevşetin.</div>
          ) : (
            <div className="sc-table-wrap">
              <table className="sc-table">
                <thead>
                  <tr>
                    {COLS.map(c => (
                      <th key={c.key}
                        className={`${c.cls} ${sortBy === c.key ? 'sc-sorted' : ''}`}
                        onClick={() => handleSort(c.key)}
                      >
                        {c.label}
                        {sortBy === c.key ? (sortDir === 'desc' ? ' ↓' : ' ↑') : ''}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {sorted.map(s => (
                    <tr key={s.ticker} className="sc-row" onClick={() => setDetail(s)}>
                      {COLS.map(c => {
                        const val = s[c.key]
                        if (c.key === 'ai_action') {
                          return (
                            <td key={c.key} className={c.cls}>
                              <span className={`sc-action ${ACTION_CLS[val] || ''}`}>{val || '—'}</span>
                            </td>
                          )
                        }
                        if (c.key === 'ticker') {
                          return (
                            <td key={c.key} className="sc-ticker-cell">
                              <span className="sc-ticker">{val}</span>
                              {s.sektor && <span className="sc-sektor">{s.sektor}</span>}
                            </td>
                          )
                        }
                        return (
                          <td key={c.key} className={`${c.cls} ${cellColor(c, val)}`}>
                            {c.fmt(val)}
                          </td>
                        )
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {results === null && !loading && (
        <div className="sc-idle">
          <div className="sc-idle-icon">⬡</div>
          <p>Filtrelerinizi ayarlayın ve <strong>Tara</strong> butonuna basın.</p>
          <p className="sc-idle-sub">BIST30 ~10sn &nbsp;·&nbsp; BIST100 ~40sn &nbsp;·&nbsp; Tüm BİST ~3-5dk</p>
        </div>
      )}
      </>}
    </div>
  )
}
