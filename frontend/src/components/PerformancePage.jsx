import { useState, useEffect } from 'react'
import './PerformancePage.css'

const OUTCOME_LABEL = { TP: 'TP Hedef', SL: 'Stop', DEVAM: 'Devam' }
const OUTCOME_CLS   = { TP: 'out-tp', SL: 'out-sl', DEVAM: 'out-open' }

function StatBox({ label, value, sub, cls }) {
  return (
    <div className={`perf-stat ${cls || ''}`}>
      <div className="perf-stat-val">{value ?? '—'}</div>
      <div className="perf-stat-lbl">{label}</div>
      {sub && <div className="perf-stat-sub">{sub}</div>}
    </div>
  )
}

export default function PerformancePage({ onBack, onTickerClick }) {
  const [data,    setData]    = useState(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)
  const [sort,    setSort]    = useState({ col: 'return_pct', dir: -1 })
  const [filter,  setFilter]  = useState('TÜMÜ') // TÜMÜ | TP | SL | DEVAM

  useEffect(() => {
    setLoading(true)
    fetch('/api/signal-performance')
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [])

  const toggleSort = (col) => {
    setSort(s => s.col === col ? { col, dir: s.dir * -1 } : { col, dir: -1 })
  }

  const SortHd = ({ col, label }) => (
    <th onClick={() => toggleSort(col)} className="sortable">
      {label}{sort.col === col ? (sort.dir < 0 ? ' ↓' : ' ↑') : ''}
    </th>
  )

  if (loading) return (
    <div className="perf-page">
      <div className="perf-header">
        <button className="back-btn" onClick={onBack}>← Geri</button>
        <h2>Sinyal Performansı</h2>
      </div>
      <div className="perf-loading">
        <div className="perf-spin">⟳</div>
        <p>Sinyal verileri yükleniyor… Bu işlem 1-2 dakika sürebilir.</p>
      </div>
    </div>
  )

  if (error) return (
    <div className="perf-page">
      <div className="perf-header">
        <button className="back-btn" onClick={onBack}>← Geri</button>
        <h2>Sinyal Performansı</h2>
      </div>
      <div className="perf-error">Hata: {error}</div>
    </div>
  )

  if (!data || data.total === 0) return (
    <div className="perf-page">
      <div className="perf-header">
        <button className="back-btn" onClick={onBack}>← Geri</button>
        <h2>Sinyal Performansı</h2>
      </div>
      <div className="perf-empty">Henüz sinyal verisi yok.</div>
    </div>
  )

  const signals = (data.signals || [])
    .filter(s => filter === 'TÜMÜ' || s.outcome === filter)
    .sort((a, b) => {
      const va = a[sort.col] ?? -999
      const vb = b[sort.col] ?? -999
      return typeof va === 'string'
        ? sort.dir * va.localeCompare(vb)
        : sort.dir * (vb - va)
    })

  const posCount  = data.pos_count ?? 0
  const posRate   = data.total ? Math.round(posCount / data.total * 100) : 0

  return (
    <div className="perf-page">
      <div className="perf-header">
        <button className="back-btn" onClick={onBack}>← Geri</button>
        <h2>Sinyal Performansı</h2>
        <span className="perf-note">İlk AL / Güçlü AL sinyali sonrası fiyat hareketi</span>
      </div>

      {/* Özet istatistikler */}
      <div className="perf-stats-row">
        <StatBox label="Toplam Sinyal"  value={data.total} />
        <StatBox label="Win Rate"
          value={data.win_rate != null ? `%${data.win_rate}` : '—'}
          sub="(kapalı işlemler)"
          cls={data.win_rate >= 50 ? 'stat-pos' : 'stat-neg'}
        />
        <StatBox label="TP Hedef"   value={data.tp_count}   cls="stat-tp" />
        <StatBox label="Stop"       value={data.sl_count}   cls="stat-sl" />
        <StatBox label="Açık"       value={data.open_count} />
        <StatBox label="Ort. Getiri"
          value={data.avg_return != null ? `%${data.avg_return > 0 ? '+' : ''}${data.avg_return}` : '—'}
          sub="tüm işlemler"
          cls={data.avg_return > 0 ? 'stat-pos' : 'stat-neg'}
        />
        <StatBox label="Pozitif Getiri"
          value={`%${posRate}`}
          sub={`${posCount} / ${data.total} hisse`}
          cls={posRate >= 50 ? 'stat-pos' : 'stat-neg'}
        />
      </div>

      {/* Filtre */}
      <div className="perf-filters">
        {['TÜMÜ', 'TP', 'SL', 'DEVAM'].map(f => (
          <button
            key={f}
            className={`pill ${filter === f ? 'pill-active' : ''}`}
            onClick={() => setFilter(f)}
          >
            {f === 'TP' ? 'TP Hedef' : f === 'SL' ? 'Stop' : f === 'DEVAM' ? 'Açık' : 'Tümü'}
            {' '}({f === 'TÜMÜ' ? data.total : (data.signals||[]).filter(s => s.outcome === f).length})
          </button>
        ))}
      </div>

      {/* Tablo */}
      <div className="perf-table-wrap">
        <table className="perf-table">
          <thead>
            <tr>
              <SortHd col="ticker"      label="Hisse" />
              <SortHd col="action"      label="Sinyal" />
              <SortHd col="sig_date"    label="Tarih" />
              <SortHd col="entry_price" label="Giriş" />
              <SortHd col="current_price" label="Güncel" />
              <SortHd col="return_pct"  label="Getiri %" />
              <SortHd col="max_pct"     label="Max %" />
              <SortHd col="tp_pct"      label="Hedef %" />
              <SortHd col="sl_pct"      label="Stop %" />
              <SortHd col="days_held"   label="Gün" />
              <SortHd col="outcome"     label="Sonuç" />
            </tr>
          </thead>
          <tbody>
            {signals.map(s => (
              <tr key={s.ticker} onClick={() => onTickerClick && onTickerClick(s.ticker)}
                  className="perf-row">
                <td className="perf-ticker">{s.ticker}</td>
                <td>
                  <span className={`sig-badge ${s.action === 'GÜÇLÜ AL' ? 'sig-strong' : 'sig-buy'}`}>
                    {s.action}
                  </span>
                </td>
                <td className="perf-date">{s.sig_date}</td>
                <td className="perf-num">{s.entry_price?.toFixed(2)}</td>
                <td className="perf-num">{s.current_price?.toFixed(2)}</td>
                <td className={`perf-num perf-ret ${s.return_pct > 0 ? 'ret-pos' : s.return_pct < 0 ? 'ret-neg' : ''}`}>
                  {s.return_pct > 0 ? '+' : ''}{s.return_pct?.toFixed(2)}%
                </td>
                <td className="perf-num ret-max">+{s.max_pct?.toFixed(2)}%</td>
                <td className="perf-num perf-tp">+{s.tp_pct?.toFixed(2)}%</td>
                <td className="perf-num perf-sl">-{s.sl_pct?.toFixed(2)}%</td>
                <td className="perf-num">{s.days_held}</td>
                <td>
                  <span className={`outcome-badge ${OUTCOME_CLS[s.outcome]}`}>
                    {OUTCOME_LABEL[s.outcome]}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
