import { useState, useCallback } from 'react'
import './PatternScanner.css'
import PatternChart from './PatternChart'

const PATTERNS_MAP = {
  double_top:        { label: 'Çift Tepe',            icon: '⌓', dir: 'bearish' },
  double_bottom:     { label: 'Çift Dip',             icon: '⌒', dir: 'bullish' },
  head_shoulders:    { label: 'Omuz-Baş-Omuz',        icon: '⌇', dir: 'bearish' },
  inv_head_shoulders:{ label: 'Ters OBO',             icon: '⌆', dir: 'bullish' },
  asc_triangle:      { label: 'Artan Üçgen',          icon: '△', dir: 'bullish' },
  desc_triangle:     { label: 'Azalan Üçgen',         icon: '▽', dir: 'bearish' },
  sym_triangle:      { label: 'Simetrik Üçgen',       icon: '◁▷', dir: 'neutral' },
  rising_wedge:      { label: 'Yükselen Kama',        icon: '⋏', dir: 'bearish' },
  falling_wedge:     { label: 'Düşen Kama',           icon: '⋎', dir: 'bullish' },
  flag:              { label: 'Bayrak',                icon: '⚑', dir: 'neutral' },
  elliott_wave:      { label: 'Elliott Dalgası',      icon: '∿', dir: 'neutral' },
}

const DIR_CLS  = { bullish: 'pat-bull', bearish: 'pat-bear', neutral: 'pat-neu' }
const DIR_ICON = { bullish: '↑', bearish: '↓', neutral: '↔' }

function ConfBar({ val }) {
  const pct = Math.round(val * 100)
  const cls = pct >= 75 ? 'conf-high' : pct >= 60 ? 'conf-mid' : 'conf-low'
  return (
    <div className="conf-wrap">
      <div className={`conf-bar ${cls}`} style={{ width: `${pct}%` }}/>
      <span className="conf-txt">{pct}%</span>
    </div>
  )
}

export default function PatternScanner({ category, onCategoryChange, onDetail }) {
  const [direction, setDirection] = useState('all')
  const [results, setResults]     = useState(null)
  const [loading, setLoading]     = useState(false)
  const [expanded, setExpanded]   = useState({})

  const doScan = useCallback(async () => {
    setLoading(true)
    setResults(null)
    setExpanded({})
    try {
      const res  = await fetch(`/api/pattern-scan?category=${category}&direction=${direction}`)
      const data = await res.json()
      setResults(data.stocks || [])
    } catch (e) { console.error(e) }
    finally { setLoading(false) }
  }, [category, direction])

  const toggle = (ticker) => setExpanded(e => ({ ...e, [ticker]: !e[ticker] }))

  return (
    <div className="ps-wrap">
      {/* Kontroller */}
      <div className="ps-controls">
        <div className="ps-ctrl-group">
          <span className="ps-label">Endeks</span>
          {['BIST30','BIST100','TÜMÜ'].map(c => (
            <button key={c}
              className={`sc-cat ${category === c ? 'sc-cat-active' : ''}`}
              onClick={() => onCategoryChange(c)}
            >{c}</button>
          ))}
        </div>
        <div className="ps-ctrl-group">
          <span className="ps-label">Yön</span>
          {[['all','Tümü'],['bullish','↑ Yükseliş'],['bearish','↓ Düşüş']].map(([k,l]) => (
            <button key={k}
              className={`sc-cat ${direction === k ? 'sc-cat-active' : ''}`}
              onClick={() => setDirection(k)}
            >{l}</button>
          ))}
        </div>
        <button className="sc-run-btn" onClick={doScan} disabled={loading}>
          {loading ? '⟳ Taranıyor…' : '⌁ Formasyonları Tara'}
        </button>
      </div>

      {/* Bilgi */}
      <div className="ps-info">
        <span className="ps-info-item">⌓ Çift Tepe/Dip</span>
        <span className="ps-info-item">⌇ Omuz-Baş-Omuz</span>
        <span className="ps-info-item">△ Üçgenler</span>
        <span className="ps-info-item">⋏ Kamalar</span>
        <span className="ps-info-item">⚑ Bayraklar</span>
        <span className="ps-info-item">∿ Elliott Wave</span>
        <span className="ps-info-note">Günlük veri · 6 aylık periyot · Confidence ≥ 60%</span>
      </div>

      {/* Loading */}
      {loading && (
        <div className="sc-loading">
          <div className="sc-spinner"/>
          <span>
            Formasyonlar hesaplanıyor…&nbsp;
            ({category === 'BIST30' ? '~20sn' : category === 'BIST100' ? '~1.5dk' : '~5dk'})
          </span>
        </div>
      )}

      {/* Sonuçlar */}
      {results !== null && !loading && (
        <div className="ps-results">
          <div className="ps-results-hdr">
            <span>{results.length} formasyonlu hisse bulundu</span>
          </div>

          {results.length === 0 ? (
            <div className="sc-empty">Seçilen kriterlere uyan formasyon bulunamadı.</div>
          ) : (
            <div className="ps-list">
              {results.map(r => {
                const top = r.top_pattern
                if (!top) return null
                const meta = PATTERNS_MAP[top.pattern] || {}
                const isOpen = expanded[r.ticker]
                return (
                  <div key={r.ticker} className="ps-card">
                    <div className="ps-card-hdr" onClick={() => toggle(r.ticker)}>
                      <div className="ps-card-left">
                        <span className="ps-ticker" onClick={e => { e.stopPropagation(); onDetail && onDetail({ticker: r.ticker, price: r.price}) }}>
                          {r.ticker}
                        </span>
                        <span className="ps-price">{r.price?.toFixed(2)} ₺</span>
                      </div>
                      <div className="ps-card-mid">
                        {r.patterns.map((p, i) => {
                          const pm = PATTERNS_MAP[p.pattern] || {}
                          const dcls = DIR_CLS[p.direction] || ''
                          return (
                            <span key={i} className={`ps-pat-badge sm ${dcls}`} title={p.description || ''}>
                              {pm.icon || '◈'} {p.name}
                            </span>
                          )
                        })}
                      </div>
                      <div className="ps-card-right">
                        <ConfBar val={top.confidence} />
                        <span className="ps-chevron">{isOpen ? '▲' : '▼'}</span>
                      </div>
                    </div>

                    {isOpen && (
                      <div className="ps-card-body">
                        {/* Grafik */}
                        <PatternChart ticker={r.ticker} patterns={r.patterns} price={r.price} />

                        {r.patterns.map((p, i) => {
                          const pm = PATTERNS_MAP[p.pattern] || {}
                          return (
                            <div key={i} className="ps-pattern-row">
                              <div className="ps-pattern-top">
                                <span className={`ps-pat-badge sm ${DIR_CLS[p.direction] || ''}`}>
                                  {pm.icon || '◈'} {p.name}
                                </span>
                                <ConfBar val={p.confidence} />
                                <span className={`ps-dir sm ${DIR_CLS[p.direction] || ''}`}>
                                  {DIR_ICON[p.direction]}
                                </span>
                              </div>
                              <p className="ps-desc">{p.description}</p>
                              <div className="ps-levels">
                                {p.target    != null && <span className="ps-lvl">🎯 Hedef: <b>{p.target?.toFixed(2)} ₺</b></span>}
                                {p.neckline  != null && <span className="ps-lvl">— Boyun: {p.neckline?.toFixed(2)} ₺</span>}
                                {p.support   != null && <span className="ps-lvl">↓ Destek: {p.support?.toFixed(2)} ₺</span>}
                                {p.resistance!= null && <span className="ps-lvl">↑ Direnç: {p.resistance?.toFixed(2)} ₺</span>}
                                {p.wave_position && <span className="ps-lvl">∿ {p.wave_position}</span>}
                                {p.fib_ratio_w3 && <span className="ps-lvl">Fib W3: {p.fib_ratio_w3}x</span>}
                              </div>
                            </div>
                          )
                        })}

                        {/* Boğa/Ayı özeti */}
                        <div className="ps-summary">
                          <span className="ps-bull-cnt">↑ {r.bullish_count} yükseliş</span>
                          <span className="ps-bear-cnt">↓ {r.bearish_count} düşüş</span>
                        </div>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {results === null && !loading && (
        <div className="sc-idle">
          <div className="sc-idle-icon">∿</div>
          <p>Klasik formasyonlar ve Elliott Wave için <strong>Formasyonları Tara</strong> butonuna basın.</p>
          <p className="sc-idle-sub">
            Her hisse için günlük fiyat verisi analiz edilir. Çift tepe/dip, OBO, üçgen, kama, bayrak, Elliott dalgası.
          </p>
        </div>
      )}
    </div>
  )
}
