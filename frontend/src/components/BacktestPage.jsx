import { useState, useEffect, useRef } from 'react'
import './BacktestPage.css'

const ACTIONS = ['GÜÇLÜ AL', 'AL', 'İZLE', 'ZAYIF', 'SAT']
const ACTION_COLOR = {
  'GÜÇLÜ AL': 'amber', 'AL': 'green', 'İZLE': 'blue', 'ZAYIF': 'orange', 'SAT': 'red'
}
const CATS = ['BIST30', 'BIST100', 'TÜMÜ']

function Pct({ val, suffix = '%' }) {
  if (val == null) return <span className="bt-null">—</span>
  const cls = val > 0 ? 'bt-pos' : val < 0 ? 'bt-neg' : 'bt-neu'
  return <span className={cls}>{val > 0 ? '+' : ''}{val}{suffix}</span>
}

function Bar({ val, max = 100 }) {
  if (val == null) return null
  const w = Math.min(100, Math.abs(val) / max * 100)
  const cls = val >= 50 ? 'bt-bar-fill-good' : 'bt-bar-fill-bad'
  return (
    <div className="bt-bar-bg">
      <div className={`bt-bar-fill ${cls}`} style={{ width: `${w}%` }} />
      <span className="bt-bar-lbl">{val}%</span>
    </div>
  )
}

export default function BacktestPage({ onBack }) {
  const [stats,       setStats]      = useState(null)
  const [progress,    setProgress]   = useState(null)
  const [params,      setParams]     = useState(null)
  const [results,     setResults]    = useState([])
  const [tab,         setTab]        = useState('stats')
  const [filterAct,   setFilterAct]  = useState('GÜÇLÜ AL')
  const [filterSetup, setFilterSetup]= useState('TÜMÜ')
  const [cat,         setCat]        = useState('BIST30')
  const [lookback,    setLookback]   = useState(365)
  const [freshOnly,   setFreshOnly]  = useState(true)
  const [mktFilter,   setMktFilter]  = useState(true)
  const [corr,        setCorr]       = useState(null)
  const [loading,     setLoading]    = useState(false)
  const [msg,         setMsg]        = useState('')
  const pollRef = useRef(null)

  // İlk yüklemede mevcut sonuçları getir
  useEffect(() => {
    fetchStats()
    fetchParams()
    fetchCorr()
  }, [])

  // filterAct değişince sonuçları güncelle
  useEffect(() => {
    if (tab === 'results') fetchResults()
    if (tab === 'corr') fetchCorr()
  }, [filterAct, tab])

  async function fetchStats() {
    try {
      const r = await fetch('/api/backtest/stats')
      const d = await r.json()
      if (d.stats) setStats(d)
    } catch {}
  }

  async function fetchParams() {
    try {
      const r = await fetch('/api/backtest/params')
      setParams(await r.json())
    } catch {}
  }

  async function fetchCorr() {
    try {
      const r = await fetch('/api/backtest/correlation')
      const d = await r.json()
      if (!d.error) setCorr(d)
    } catch {}
  }

  async function fetchResults() {
    try {
      const r = await fetch(`/api/backtest/results?action=${encodeURIComponent(filterAct)}&limit=200`)
      const d = await r.json()
      setResults(d.results || [])
    } catch {}
  }

  function startPoll() {
    if (pollRef.current) clearInterval(pollRef.current)
    pollRef.current = setInterval(async () => {
      try {
        const r = await fetch('/api/backtest/progress')
        const p = await r.json()
        setProgress(p)
        if (!p.running) {
          clearInterval(pollRef.current)
          setLoading(false)
          await fetchStats()
          if (p.error) {
            setMsg(`Hata: ${p.error}`)
          } else {
            setMsg('Backtest tamamlandı!')
            setTimeout(() => setMsg(''), 4000)
          }
        }
      } catch {}
    }, 2000)
  }

  async function runBacktest() {
    setLoading(true)
    setMsg('')
    try {
      const r = await fetch('/api/backtest/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          category: cat, lookback_days: lookback, step_days: 1,
          fresh_signals_only: freshOnly, market_filter: mktFilter,
        }),
      })
      const d = await r.json()
      if (d.error) { setMsg(d.error); setLoading(false); return }
      setProgress(d.progress)
      startPoll()
    } catch (e) {
      setMsg('Bağlantı hatası')
      setLoading(false)
    }
  }

  async function runEvolve() {
    setMsg('Parametreler optimize ediliyor…')
    try {
      const r = await fetch('/api/backtest/evolve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_action: 'GÜÇLÜ AL' }),
      })
      const d = await r.json()
      if (d.params) setParams(d.params)
      setMsg(d.message || 'Tamamlandı')
      setTimeout(() => setMsg(''), 4000)
    } catch {
      setMsg('Evolver hatası')
    }
  }

  const actionStats = stats?.stats?.by_action || {}
  const setupStats  = stats?.stats?.by_setup  || {}

  const SETUP_META = {
    'KIRILIM': { label: '💥 KIRILIM',  desc: 'Hacimli kırılım + momentum', cls: 'bt-setup-kirilim' },
    'DÖNÜŞ':   { label: '↩ DÖNÜŞ',    desc: 'Aşırı satım + destek + toparlanma', cls: 'bt-setup-donus' },
    'STANDART':{ label: '◉ STANDART', desc: 'Diğer sinyaller', cls: 'bt-setup-standart' },
  }

  return (
    <div className="bt-page">
      {/* Header */}
      <div className="bt-header">
        <button className="bt-back" onClick={onBack}>← Geri</button>
        <div className="bt-title">
          <span className="bt-icon">⚗</span>
          <span>Backtest & Evolver</span>
        </div>
        <div className="bt-tabs">
          {['stats', 'results', 'corr', 'params'].map(t => (
            <button key={t}
              className={`bt-tab ${tab === t ? 'bt-tab-active' : ''}`}
              onClick={() => { setTab(t); if (t === 'results') fetchResults(); if (t === 'corr') fetchCorr() }}
            >
              {t === 'stats' ? '📊 İstatistik' : t === 'results' ? '📋 Sinyaller' : t === 'corr' ? '🔬 Korelasyon' : '⚙ Parametreler'}
            </button>
          ))}
        </div>
      </div>

      {/* Kontroller */}
      <div className="bt-controls">
        <div className="bt-ctrl-group">
          <label>Endeks</label>
          {CATS.map(c => (
            <button key={c} className={`bt-pill ${cat === c ? 'bt-pill-active' : ''}`}
              onClick={() => setCat(c)}>{c}</button>
          ))}
        </div>
        <div className="bt-ctrl-group">
          <label>Geçmiş</label>
          {[90, 180, 365, 730].map(d => (
            <button key={d} className={`bt-pill ${lookback === d ? 'bt-pill-active' : ''}`}
              onClick={() => setLookback(d)}>{d === 730 ? '2 Yıl' : d === 365 ? '1 Yıl' : `${d}g`}</button>
          ))}
        </div>
        <div className="bt-ctrl-group">
          <label>Taze Sinyal</label>
          <button className={`bt-pill ${freshOnly ? 'bt-pill-active' : ''}`}
            onClick={() => setFreshOnly(v => !v)} title="Sadece sinyalin ilk çıktığı günü say">
            {freshOnly ? '✓ Açık' : '✗ Kapalı'}
          </button>
        </div>
        <div className="bt-ctrl-group">
          <label>Piyasa Filtresi</label>
          <button className={`bt-pill ${mktFilter ? 'bt-pill-active' : ''}`}
            onClick={() => setMktFilter(v => !v)} title="Ayı piyasasında AL sinyallerini say">
            {mktFilter ? '✓ Açık' : '✗ Kapalı'}
          </button>
        </div>
        <button className="bt-run-btn" onClick={runBacktest} disabled={loading}>
          {loading ? '⟳ Çalışıyor…' : '▶ Backtest Başlat'}
        </button>
        {stats && (
          <button className="bt-evolve-btn" onClick={runEvolve} disabled={loading}>
            🧬 Parametreleri Optimize Et
          </button>
        )}
      </div>

      {/* İlerleme */}
      {progress?.running && (
        <div className="bt-progress">
          <div className="bt-prog-bar">
            <div className="bt-prog-fill"
              style={{ width: `${progress.total > 0 ? (progress.done / progress.total) * 100 : 0}%` }} />
          </div>
          <span className="bt-prog-txt">
            {progress.done}/{progress.total} — {progress.current}
          </span>
        </div>
      )}
      {msg && <div className="bt-msg">{msg}</div>}

      {/* İçerik */}
      {tab === 'stats' && (
        <div className="bt-content">
          {!stats ? (
            <div className="bt-empty">Henüz backtest çalıştırılmadı. Yukarıdan başlatın.</div>
          ) : (
            <>
              {/* Genel özet */}
              <div className="bt-summary">
                <div className="bt-sum-card">
                  <div className="bt-sum-val">{stats.total_signals?.toLocaleString()}</div>
                  <div className="bt-sum-lbl">Toplam Sinyal</div>
                </div>
                <div className="bt-sum-card">
                  <div className="bt-sum-val">{stats.stats?.overall?.tickers}</div>
                  <div className="bt-sum-lbl">Hisse</div>
                </div>
                <div className="bt-sum-card">
                  <div className={`bt-sum-val ${(stats.stats?.overall?.win_rate_1w || 0) >= 50 ? 'bt-pos' : 'bt-neg'}`}>
                    {stats.stats?.overall?.win_rate_1w}%
                  </div>
                  <div className="bt-sum-lbl">Genel Win Rate (1 Hafta)</div>
                </div>
                <div className="bt-sum-card">
                  <div className={`bt-sum-val ${(stats.stats?.overall?.avg_return_1w || 0) >= 0 ? 'bt-pos' : 'bt-neg'}`}>
                    {stats.stats?.overall?.avg_return_1w != null ? `${stats.stats.overall.avg_return_1w > 0 ? '+' : ''}${stats.stats.overall.avg_return_1w}%` : '—'}
                  </div>
                  <div className="bt-sum-lbl">Ort. Getiri (1H)</div>
                </div>
              </div>

              {/* Sinyal tablosu */}
              <div className="bt-table-wrap">
                <table className="bt-table">
                  <thead>
                    <tr>
                      <th>Sinyal</th>
                      <th>Adet</th>
                      <th>Win Rate 1 Gün</th>
                      <th>Win Rate 1 Hafta</th>
                      <th>Win Rate 1 Ay</th>
                      <th>Ort. Getiri 1 Hafta</th>
                      <th>Ort. Getiri 1 Ay</th>
                      <th>En İyi 1 Ay</th>
                      <th>En Kötü 1 Ay</th>
                      <th>TP1 Vuruş</th>
                      <th>SL Vuruş</th>
                      <th>Ort. Gün → TP1</th>
                      <th>Beklenen Değer (1 Hafta)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ACTIONS.map(a => {
                      const s = actionStats[a]
                      if (!s) return null
                      return (
                        <tr key={a} className={`bt-row-${ACTION_COLOR[a]}`}>
                          <td>
                            <span className={`bt-action-badge bt-badge-${ACTION_COLOR[a]}`}>{a}</span>
                            {s.low_sample && <span className="bt-warn" title="Az sinyal — istatistik güvenilir değil"> ⚠</span>}
                          </td>
                          <td className="bt-num">{s.count}</td>
                          <td><Bar val={s.win_rate_1d} /></td>
                          <td><Bar val={s.win_rate_1w} /></td>
                          <td><Bar val={s.win_rate_1mo} /></td>
                          <td><Pct val={s.avg_return_1w} /></td>
                          <td><Pct val={s.avg_return_1mo} /></td>
                          <td><Pct val={s.best_1mo} /></td>
                          <td><Pct val={s.worst_1mo} /></td>
                          <td><Bar val={s.tp1_hit_rate} /></td>
                          <td><Bar val={s.sl_hit_rate} /></td>
                          <td className="bt-num">{s.avg_days_to_tp1 ?? '—'}</td>
                          <td><Pct val={s.expected_value_1w} /></td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>

              {/* Win Rate grafik */}
              <div className="bt-chart-row">
                {ACTIONS.map(a => {
                  const s = actionStats[a]
                  if (!s) return null
                  const wr = s.win_rate_1w || 0
                  return (
                    <div key={a} className="bt-wr-card">
                      <div className="bt-wr-title">
                        <span className={`bt-badge bt-badge-${ACTION_COLOR[a]}`}>{a}</span>
                      </div>
                      <div className="bt-wr-gauge">
                        <svg viewBox="0 0 100 60" className="bt-gauge-svg">
                          <path d="M 10 55 A 40 40 0 0 1 90 55" fill="none" stroke="#1e293b" strokeWidth="10"/>
                          <path d="M 10 55 A 40 40 0 0 1 90 55" fill="none"
                            stroke={wr >= 55 ? '#22c55e' : wr >= 45 ? '#f59e0b' : '#ef4444'}
                            strokeWidth="10"
                            strokeDasharray={`${wr * 1.257} 125.7`}
                            strokeLinecap="round"
                          />
                          <text x="50" y="52" textAnchor="middle" className="bt-gauge-txt">{wr}%</text>
                        </svg>
                      </div>
                      <div className="bt-wr-sub">
                        {s.low_sample && <span className="bt-warn">⚠ Az veri · </span>}
                        {s.count} sinyal · EV: <Pct val={s.expected_value_1w} />
                      </div>
                    </div>
                  )
                })}
              </div>

              {/* Setup Analizi — hedef: +%3-5 yakalama */}
              {Object.keys(setupStats).length > 0 && (
                <>
                  <div className="bt-section-title">🎯 Setup Türü Analizi — Hedef: +%3-5+ Hamleler</div>
                  <div className="bt-table-wrap" style={{ marginBottom: 12 }}>
                    <table className="bt-table">
                      <thead>
                        <tr>
                          <th>Setup</th>
                          <th>Açıklama</th>
                          <th>Adet</th>
                          <th>Win Rate 1 Hafta</th>
                          <th>Ort. Getiri 1 Hafta</th>
                          <th>%3+ Oran</th>
                          <th>%5+ Oran</th>
                          <th>TP1 Vuruş</th>
                          <th>SL Vuruş</th>
                          <th>Beklenen Değer</th>
                        </tr>
                      </thead>
                      <tbody>
                        {['KIRILIM', 'DÖNÜŞ', 'STANDART'].map(st => {
                          const s = setupStats[st]
                          if (!s) return null
                          const meta = SETUP_META[st]
                          return (
                            <tr key={st}>
                              <td><span className={`bt-action-badge ${meta.cls}`}>{meta.label}</span>
                                {s.low_sample && <span className="bt-warn" title="Az sinyal"> ⚠</span>}
                              </td>
                              <td style={{ color: '#64748b', fontSize: 12 }}>{meta.desc}</td>
                              <td className="bt-num">{s.count}</td>
                              <td><Bar val={s.win_rate_1w} /></td>
                              <td><Pct val={s.avg_return_1w} /></td>
                              <td className="bt-num" style={{ color: s.pct_3plus >= 20 ? '#22c55e' : '#64748b' }}>
                                {s.pct_3plus != null ? `${s.pct_3plus}%` : '—'}
                              </td>
                              <td className="bt-num" style={{ color: s.pct_5plus >= 15 ? '#22c55e' : '#64748b' }}>
                                {s.pct_5plus != null ? `${s.pct_5plus}%` : '—'}
                              </td>
                              <td><Bar val={s.tp1_hit_rate} /></td>
                              <td><Bar val={s.sl_hit_rate} /></td>
                              <td><Pct val={s.expected_value_1w} /></td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                  <div className="bt-evolve-note" style={{ marginBottom: 24 }}>
                    <b>💥 KIRILIM:</b> Yükseliş BOS + hacim &gt;1.8x ortalama + 5G momentum &gt;%3 — momentum yakalama stratejisi.<br/>
                    <b>↩ DÖNÜŞ:</b> RSI &lt;35 + destek seviyesinde — aşırı satım geri dönüş stratejisi.<br/>
                    Hedef: "%3+ Oran" sütununda KIRILIM veya DÖNÜŞ setupları için <b>%20+</b> görülmesi,
                    yani her 5 sinyalden 1'inin +%3 kazandırması sürdürülebilir bir edge'dir.
                  </div>
                </>
              )}
            </>
          )}
        </div>
      )}

      {tab === 'results' && (
        <div className="bt-content">
          <div className="bt-filter-row">
            {ACTIONS.map(a => (
              <button key={a}
                className={`bt-pill ${filterAct === a ? `bt-pill-active bt-pill-${ACTION_COLOR[a]}` : ''}`}
                onClick={() => setFilterAct(a)}>{a}</button>
            ))}
            <span style={{ color: '#334155', margin: '0 4px' }}>|</span>
            {['TÜMÜ', 'KIRILIM', 'DÖNÜŞ', 'STANDART'].map(s => (
              <button key={s}
                className={`bt-pill ${filterSetup === s ? 'bt-pill-active' : ''}`}
                style={filterSetup === s && s !== 'TÜMÜ' ? {
                  background: s === 'KIRILIM' ? '#172554' : '#14532d',
                  color: s === 'KIRILIM' ? '#93c5fd' : '#86efac',
                  borderColor: s === 'KIRILIM' ? '#1d4ed8' : '#16a34a',
                } : {}}
                onClick={() => setFilterSetup(s)}>{s}</button>
            ))}
          </div>
          {results.filter(r => filterSetup === 'TÜMÜ' || r.setup_type === filterSetup).length === 0 ? (
            <div className="bt-empty">Sonuç yok</div>
          ) : (
            <div className="bt-table-wrap">
              <table className="bt-table bt-results-table">
                <thead>
                  <tr>
                    <th>Hisse</th>
                    <th>Tarih</th>
                    <th>Setup</th>
                    <th>Skor</th>
                    <th>Fiyat</th>
                    <th>1 Gün</th>
                    <th>3 Gün</th>
                    <th>1 Hafta</th>
                    <th>2 Hafta</th>
                    <th>1 Ay</th>
                    <th>TP1</th>
                    <th>SL</th>
                    <th>TP1 Vuruş</th>
                    <th>SL Vuruş</th>
                    <th>Gün→TP1</th>
                  </tr>
                </thead>
                <tbody>
                  {results.filter(r => filterSetup === 'TÜMÜ' || r.setup_type === filterSetup).map((r, i) => {
                    const setupMeta = SETUP_META[r.setup_type] || SETUP_META['STANDART']
                    return (
                    <tr key={i} className={r.return_1w > 0 ? 'bt-win-row' : r.return_1w < 0 ? 'bt-loss-row' : ''}>
                      <td className="bt-ticker">{r.ticker}</td>
                      <td className="bt-date">{r.signal_date}</td>
                      <td><span className={`bt-action-badge ${setupMeta.cls}`} style={{ fontSize: 10 }}>{setupMeta.label}</span></td>
                      <td className="bt-num">{r.score}</td>
                      <td className="bt-num">{r.price?.toFixed(2)}</td>
                      <td><Pct val={r.return_1d} /></td>
                      <td><Pct val={r.return_3d} /></td>
                      <td><Pct val={r.return_1w} /></td>
                      <td><Pct val={r.return_2w} /></td>
                      <td><Pct val={r.return_1mo} /></td>
                      <td className="bt-num">{r.tp1?.toFixed(2) ?? '—'}</td>
                      <td className="bt-num">{r.sl?.toFixed(2) ?? '—'}</td>
                      <td>{r.hit_tp1 ? <span className="bt-hit">✓</span> : <span className="bt-miss">✗</span>}</td>
                      <td>{r.hit_sl  ? <span className="bt-hit-sl">✓</span> : <span className="bt-miss">✗</span>}</td>
                      <td className="bt-num">{r.days_to_tp1 ?? '—'}</td>
                    </tr>
                  )})}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {tab === 'corr' && (
        <div className="bt-content">
          {!corr ? (
            <div className="bt-empty">Önce backtest çalıştırın.</div>
          ) : (
            <>
              {/* Korelasyon özet kartları */}
              <div className="bt-summary">
                <div className="bt-sum-card">
                  <div className={`bt-sum-val ${Math.abs(corr.score_return_corr_1w || 0) > 0.15 ? 'bt-pos' : 'bt-neg'}`}>
                    {corr.score_return_corr_1w ?? '—'}
                  </div>
                  <div className="bt-sum-lbl">Skor↔Getiri Korelasyon (1 Hafta)</div>
                </div>
                <div className="bt-sum-card">
                  <div className={`bt-sum-val ${Math.abs(corr.score_return_corr_1mo || 0) > 0.15 ? 'bt-pos' : 'bt-neg'}`}>
                    {corr.score_return_corr_1mo ?? '—'}
                  </div>
                  <div className="bt-sum-lbl">Skor↔Getiri Korelasyon (1 Ay)</div>
                </div>
                {corr.best_threshold && (
                  <div className="bt-sum-card">
                    <div className="bt-sum-val bt-pos">{corr.best_threshold}+</div>
                    <div className="bt-sum-lbl">En İyi Skor Eşiği (EV: {corr.best_threshold_ev}%)</div>
                  </div>
                )}
              </div>

              {/* Yorum */}
              <div className={`bt-corr-note ${Math.abs(corr.score_return_corr_1w || 0) < 0.1 ? 'bt-corr-warn' : 'bt-corr-ok'}`}>
                {Math.abs(corr.score_return_corr_1w || 0) < 0.1
                  ? '⚠ Skor ile gelecek getiri arasında anlamlı korelasyon yok. Backtest\'i yeni momentum faktörüyle yeniden çalıştırın.'
                  : `✓ Skor sistemi öngörü gücü taşıyor (r=${corr.score_return_corr_1w}). Eşik kalibrasyonu için Evolver çalıştırın.`
                }
              </div>

              {/* Skor bucket tablosu */}
              <div className="bt-table-wrap">
                <table className="bt-table">
                  <thead>
                    <tr>
                      <th>Skor Aralığı</th>
                      <th>Sinyal Sayısı</th>
                      <th>Win Rate 1 Hafta</th>
                      <th>Ort. Getiri 1 Hafta</th>
                      <th>Win Rate 1 Ay</th>
                      <th>Ort. Getiri 1 Ay</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(corr.score_buckets || []).map((b, i) => (
                      <tr key={i}>
                        <td className="bt-score-range">{b.range}</td>
                        <td className="bt-num">{b.count}</td>
                        <td><Bar val={b.win_rate_1w} /></td>
                        <td><Pct val={b.avg_return_1w} /></td>
                        <td><Bar val={b.win_rate_1mo} /></td>
                        <td><Pct val={b.avg_return_1mo} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="bt-evolve-note">
                <b>📐 Korelasyon nasıl yorumlanır?</b><br/>
                Korelasyon 0'a yakınsa skor geleceği tahmin etmiyor demektir.
                Hedef: <b>|r| &gt; 0.15</b> (anlamlı), <b>|r| &gt; 0.30</b> (güçlü).<br/>
                Momentum faktörü eklendikten sonra backtest'i yeniden çalıştırın.
                Korelasyon arttıysa skor sistemi iyileşmiş demektir.
              </div>
            </>
          )}
        </div>
      )}

      {tab === 'params' && params && (
        <div className="bt-content bt-params-content">
          <div className="bt-params-grid">
            <div className="bt-param-card">
              <div className="bt-param-title">Skor Eşikleri</div>
              <div className="bt-param-body">
                {['GÜÇLÜ AL', 'AL', 'İZLE', 'ZAYIF'].map((a, i) => (
                  <div key={a} className="bt-param-row">
                    <span className={`bt-badge bt-badge-${ACTION_COLOR[a]}`}>{a}</span>
                    <span className="bt-param-val">{params.thresholds?.[i]} +</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="bt-param-card">
              <div className="bt-param-title">Ağırlıklar</div>
              <div className="bt-param-body">
                <div className="bt-param-row">
                  <span>Günlük (1d)</span>
                  <span className="bt-param-val">{((params.weights_1d || 0.6) * 100).toFixed(0)}%</span>
                </div>
                <div className="bt-param-row">
                  <span>Haftalık (1w)</span>
                  <span className="bt-param-val">{((1 - (params.weights_1d || 0.6)) * 100).toFixed(0)}%</span>
                </div>
                <div className="bt-param-row">
                  <span>MTF Bonus</span>
                  <span className="bt-param-val">±{params.mtf_bonus}</span>
                </div>
              </div>
            </div>
            {params.evolved_at && (
              <div className="bt-param-card">
                <div className="bt-param-title">Son Optimizasyon</div>
                <div className="bt-param-body">
                  <div className="bt-param-row">
                    <span>Tarih</span>
                    <span className="bt-param-val">{params.evolved_at}</span>
                  </div>
                  {params.target_ev != null && (
                    <div className="bt-param-row">
                      <span>Hedef Beklenen Değer</span>
                      <Pct val={params.target_ev} />
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
          <div className="bt-evolve-note">
            <b>🧬 Nasıl çalışır?</b> Evolver, geçmiş sinyalleri farklı eşik kombinasyonlarıyla yeniden
            değerlendirerek GÜÇLÜ AL sinyallerinin beklenen getirisini (beklenen değer) maksimize eden
            parametreleri bulur ve kaydeder. Sonraki taramalarda bu parametreler kullanılmaya devam eder.
          </div>
        </div>
      )}
    </div>
  )
}
