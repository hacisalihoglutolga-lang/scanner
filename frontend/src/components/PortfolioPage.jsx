import { useState } from 'react'
import './PortfolioPage.css'

const DEFAULT_HOLDINGS = [
  { ticker: 'INFO',  shares: 56000, avg_cost: 3.52  },
  { ticker: 'EKGYO', shares: 4933,  avg_cost: 20.00 },
  { ticker: 'ENTRA', shares: 12000, avg_cost: 10.39 },
  { ticker: 'BRKVY', shares: 3367,  avg_cost: 94.85 },
  { ticker: 'ELITE', shares: 4400,  avg_cost: 29.00 },
  { ticker: 'YEOTK', shares: 1,     avg_cost: 49.84 },
  { ticker: 'GOKNR', shares: 8160,  avg_cost: 20.56 },
]

const FRAMEWORKS = [
  { key: 'gs',         icon: '🏦', label: 'Goldman Sachs',    subtitle: 'Temel Analiz' },
  { key: 'ms',         icon: '📈', label: 'Morgan Stanley',   subtitle: 'Teknik Analiz' },
  { key: 'bw',         icon: '🛡',  label: 'Bridgewater',      subtitle: 'Risk Değerlendirmesi' },
  { key: 'jp',         icon: '💹', label: 'JPMorgan',         subtitle: 'Kazanç Analizi' },
  { key: 'blk',        icon: '💰', label: 'BlackRock',        subtitle: 'Temettü Geliri' },
  { key: 'cit',        icon: '🌐', label: 'Citadel',          subtitle: 'Sektör Rotasyonu' },
  { key: 'ren',        icon: '🔬', label: 'Renaissance',      subtitle: 'Kantitatif Tarama' },
  { key: 'two_sigma',  icon: '🌍', label: 'Two Sigma',        subtitle: 'Makro Görünüm' },
]

export default function PortfolioPage({ onBack, onTickerClick }) {
  const [holdings, setHoldings] = useState(DEFAULT_HOLDINGS)
  const [result,   setResult]   = useState(null)
  const [loading,  setLoading]  = useState(false)
  const [activeTab, setActiveTab] = useState('gs')
  const [editMode, setEditMode]   = useState(false)

  async function analyze() {
    setLoading(true)
    setResult(null)
    try {
      const res  = await fetch('/api/portfolio/analyze', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ holdings }),
      })
      const data = await res.json()
      setResult(data)
    } catch (e) {
      alert('Analiz hatası: ' + e.message)
    } finally {
      setLoading(false)
    }
  }

  function updateHolding(i, field, value) {
    setHoldings(prev => prev.map((h, idx) =>
      idx === i ? { ...h, [field]: field === 'ticker' ? value.toUpperCase() : parseFloat(value) || 0 } : h
    ))
  }

  function addRow() {
    setHoldings(prev => [...prev, { ticker: '', shares: 0, avg_cost: 0 }])
  }

  function removeRow(i) {
    setHoldings(prev => prev.filter((_, idx) => idx !== i))
  }

  const raw = result?.raw
  const totalVal  = raw?.total_value || 0
  const totalCost = Object.values(raw?.stocks || {}).reduce((s, v) => s + v.cost, 0)
  const totalPnL  = totalVal - totalCost
  const totalPnLPct = totalCost > 0 ? ((totalVal - totalCost) / totalCost * 100) : 0

  return (
    <div className="pp-page">

      {/* ── Header ── */}
      <div className="pp-header">
        <div className="pp-hdr-left">
          <button className="pp-back-btn" onClick={onBack}>← Tarayıcı</button>
          <div className="pp-title-wrap">
            <span className="pp-logo">◈ THS</span>
            <span className="pp-subtitle">Portföy Analiz Terminali</span>
          </div>
        </div>
        <div className="pp-hdr-right">
          <button className="pp-edit-btn" onClick={() => setEditMode(e => !e)}>
            {editMode ? '✓ Kaydet' : '✏ Düzenle'}
          </button>
          <button className="pp-analyze-btn" onClick={analyze} disabled={loading}>
            {loading ? <><span className="pp-spin">⟳</span> Analiz ediliyor…</> : '⬡ Analiz Et'}
          </button>
        </div>
      </div>

      {/* ── Portföy Tablosu ── */}
      <div className="pp-portfolio-section">
        <div className="pp-section-title">📊 Portföy Varlıkları</div>
        <div className="pp-table-wrap">
          <table className="pp-table">
            <thead>
              <tr>
                <th>Hisse</th>
                <th>Lot / Adet</th>
                <th>Ortalama Maliyet</th>
                {result && <><th>Güncel Fiyat</th><th>Değer</th><th>K/Z</th><th>Ağırlık</th></>}
                {editMode && <th></th>}
              </tr>
            </thead>
            <tbody>
              {holdings.map((h, i) => {
                const s = raw?.stocks?.[h.ticker]
                return (
                  <tr key={i}>
                    <td>
                      {editMode
                        ? <input className="pp-cell-input" value={h.ticker} onChange={e => updateHolding(i, 'ticker', e.target.value)} />
                        : <span className="pp-ticker-cell pp-ticker-btn" onClick={() => onTickerClick?.(h.ticker)}>{h.ticker}</span>
                      }
                    </td>
                    <td>
                      {editMode
                        ? <input className="pp-cell-input" type="number" value={h.shares} onChange={e => updateHolding(i, 'shares', e.target.value)} />
                        : h.shares.toLocaleString('tr-TR')
                      }
                    </td>
                    <td>
                      {editMode
                        ? <input className="pp-cell-input" type="number" step="0.01" value={h.avg_cost} onChange={e => updateHolding(i, 'avg_cost', e.target.value)} />
                        : `₺${h.avg_cost.toLocaleString('tr-TR', {minimumFractionDigits: 2})}`
                      }
                    </td>
                    {result && (
                      <>
                        <td className="pp-num">{s ? `₺${s.price.toLocaleString('tr-TR', {minimumFractionDigits: 2})}` : '—'}</td>
                        <td className="pp-num">{s ? `₺${s.value.toLocaleString('tr-TR', {minimumFractionDigits: 0})}` : '—'}</td>
                        <td className={`pp-num ${s?.pnl_pct >= 0 ? 'pp-pos' : 'pp-neg'}`}>
                          {s ? `${s.pnl_pct >= 0 ? '+' : ''}${s.pnl_pct.toFixed(2)}%` : '—'}
                        </td>
                        <td className="pp-num pp-weight">
                          {s ? (
                            <div className="pp-weight-bar-wrap">
                              <div className="pp-weight-bar" style={{width: `${s.weight}%`}} />
                              <span>{s.weight}%</span>
                            </div>
                          ) : '—'}
                        </td>
                      </>
                    )}
                    {editMode && (
                      <td><button className="pp-remove-btn" onClick={() => removeRow(i)}>✕</button></td>
                    )}
                  </tr>
                )
              })}
            </tbody>
          </table>
          {editMode && (
            <button className="pp-add-row-btn" onClick={addRow}>+ Hisse Ekle</button>
          )}
        </div>

        {/* Portföy Özet */}
        {result && (
          <div className="pp-summary-row">
            <SumCard label="Toplam Değer"  val={`₺${totalVal.toLocaleString('tr-TR', {minimumFractionDigits: 0})}`} />
            <SumCard label="Toplam Maliyet" val={`₺${totalCost.toLocaleString('tr-TR', {minimumFractionDigits: 0})}`} />
            <SumCard label="K/Z"
              val={`${totalPnL >= 0 ? '+' : ''}₺${Math.abs(totalPnL).toLocaleString('tr-TR', {minimumFractionDigits: 0})}`}
              color={totalPnL >= 0 ? '#22c55e' : '#ef4444'}
            />
            <SumCard label="K/Z %"
              val={`${totalPnLPct >= 0 ? '+' : ''}${totalPnLPct.toFixed(2)}%`}
              color={totalPnLPct >= 0 ? '#22c55e' : '#ef4444'}
            />
            <SumCard label="Hisse Sayısı"  val={Object.keys(raw?.stocks || {}).length} />
            <SumCard label="Ort. AI Skoru"
              val={(() => {
                const scores = Object.values(raw?.stocks || {}).map(s => s.analysis?.ai_score || 0)
                return scores.length ? (scores.reduce((a,b) => a+b, 0) / scores.length).toFixed(1) + '/10' : '—'
              })()}
            />
          </div>
        )}
      </div>

      {/* ── Loading ── */}
      {loading && (
        <div className="pp-loading">
          <div className="pp-loading-inner">
            <div className="pp-big-spin">⟳</div>
            <div className="pp-loading-title">Kurumsal Analiz Yapılıyor</div>
            <div className="pp-loading-steps">
              <div className="pp-step">📡 Yahoo Finance'den veri çekiliyor…</div>
              <div className="pp-step">🧮 8 analiz çerçevesi hesaplanıyor…</div>
              <div className="pp-step">🤖 AI narrative üretiliyor (Claude)…</div>
            </div>
          </div>
        </div>
      )}

      {/* ── Analiz Sonuçları ── */}
      {result && !loading && (
        <div className="pp-results">

          {/* Framework Sekmeler */}
          <div className="pp-fw-tabs">
            {FRAMEWORKS.map(fw => (
              <button key={fw.key}
                className={`pp-fw-tab ${activeTab === fw.key ? 'pp-fw-tab-active' : ''}`}
                onClick={() => setActiveTab(fw.key)}
              >
                <span className="pp-fw-icon">{fw.icon}</span>
                <span className="pp-fw-label">{fw.label}</span>
                <span className="pp-fw-sub">{fw.subtitle}</span>
              </button>
            ))}
          </div>

          {/* Framework İçeriği */}
          <div className="pp-fw-content">
            {activeTab === 'gs'  && <GsPanel  data={result} />}
            {activeTab === 'ms'  && <MsPanel  data={result} />}
            {activeTab === 'bw'  && <BwPanel  data={result} />}
            {activeTab === 'jp'  && <JpPanel  data={result} />}
            {activeTab === 'blk' && <BlkPanel data={result} />}
            {activeTab === 'cit' && <CitPanel data={result} />}
            {activeTab === 'ren' && <RenPanel data={result} />}
            {activeTab === 'two_sigma' && <TwoSigmaPanel data={result} />}
          </div>
        </div>
      )}

      {/* İlk açılış prompt */}
      {!result && !loading && (
        <div className="pp-empty-prompt">
          <div className="pp-empty-icon">◈</div>
          <div className="pp-empty-title">Portföyünü Analiz Et</div>
          <div className="pp-empty-sub">Hisseleri düzenle ve "Analiz Et" butonuna tıkla.<br/>Goldman Sachs • Morgan Stanley • Bridgewater • Renaissance ve daha fazlası</div>
          <button className="pp-analyze-btn-big" onClick={analyze} disabled={loading}>
            ⬡ Kurumsal Analizi Başlat
          </button>
        </div>
      )}
    </div>
  )
}


// ─── Goldman Sachs — Temel Analiz ────────────────────────────────────────────
function GsPanel({ data }) {
  const gs  = data.gs_fundamental
  const ai  = data.ai?.gs
  return (
    <FwPanel icon="🏦" title="Goldman Sachs" subtitle="Equity Research — Temel Analiz Notu">
      <AiBox text={ai} firm="Goldman Sachs" color="#3b82f6" />
      <div className="pp-metrics-header">
        <MetricBadge label="Port. F/K"   val={gs.port_fk}   />
        <MetricBadge label="Port. PD/DD" val={gs.port_pddd} />
        <MetricBadge label="Port. ROE"   val={gs.port_roe ? gs.port_roe + '%' : null} />
        <MetricBadge label="Net Marj"    val={gs.port_net_margin ? gs.port_net_margin + '%' : null} />
        <MetricBadge label="Temel Skor"  val={gs.port_fund_score ? gs.port_fund_score + '/10' : null} color="#f59e0b" />
      </div>
      <StockTable
        rows={gs.rows}
        cols={[
          { key: 'weight',     label: 'Ağırlık', fmt: v => v + '%' },
          { key: 'fk',         label: 'F/K',     good: v => v > 0 && v < 20, bad: v => v > 40 },
          { key: 'pd_dd',      label: 'PD/DD',   good: v => v < 2, bad: v => v > 5 },
          { key: 'roe',        label: 'ROE %',   fmt: v => v + '%', good: v => v > 15, bad: v => v < 0 },
          { key: 'net_margin', label: 'Net Marj %', fmt: v => v + '%', good: v => v > 10, bad: v => v < 0 },
          { key: 'rev_growth', label: 'Gelir Büy %', fmt: v => v + '%', good: v => v > 10, bad: v => v < 0 },
          { key: 'fund_score', label: 'Temel Skor', fmt: v => v + '/10', good: v => v >= 7, bad: v => v < 4 },
          { key: 'action',     label: 'Sinyal', action: true },
        ]}
      />
    </FwPanel>
  )
}


// ─── Morgan Stanley — Teknik Analiz ──────────────────────────────────────────
function MsPanel({ data }) {
  const ms = data.ms_technical
  const ai = data.ai?.ms
  return (
    <FwPanel icon="📈" title="Morgan Stanley" subtitle="Technical Strategy — Teknik Analiz Notu">
      <AiBox text={ai} firm="Morgan Stanley" color="#10b981" />
      <div className="pp-metrics-header">
        <MetricBadge label="Boğa Trendi" val={`${ms.bull_count}/${ms.total}`} color={ms.bull_count > ms.total/2 ? '#22c55e' : '#ef4444'} />
        <MetricBadge label="Yükseliş Yapısı" val={`${ms.ms_count}/${ms.total}`} color={ms.ms_count > ms.total/2 ? '#22c55e' : '#ef4444'} />
      </div>
      <StockTable
        rows={ms.rows}
        cols={[
          { key: 'weight',      label: 'Ağırlık',  fmt: v => v + '%' },
          { key: 'price',       label: 'Fiyat',    fmt: v => '₺' + v },
          { key: 'trend',       label: 'Trend',    trend: true },
          { key: 'structure',   label: 'Yapı',     structure: true },
          { key: 'rsi',         label: 'RSI',      good: v => v >= 40 && v <= 60, bad: v => v > 70 },
          { key: 'rr',          label: 'R:R',      fmt: v => v ? '1:' + v : '—', good: v => v >= 2 },
          { key: 'weekly_bias', label: 'Haftalık', bias: true },
          { key: 'action',      label: 'Sinyal',   action: true },
        ]}
      />
    </FwPanel>
  )
}


// ─── Bridgewater — Risk ───────────────────────────────────────────────────────
function BwPanel({ data }) {
  const bw = data.bridgewater_risk
  const ai = data.ai?.bw
  return (
    <FwPanel icon="🛡" title="Bridgewater Associates" subtitle="Risk Assessment — Risk Değerlendirmesi">
      <AiBox text={ai} firm="Bridgewater" color="#a78bfa" />
      <div className="pp-metrics-header">
        <MetricBadge label="Port. Volatilite" val={bw.port_vol ? bw.port_vol + '%' : '—'} bad={bw.port_vol > 30} />
        <MetricBadge label="Konsantrasyon"    val={bw.concentration} color={bw.concentration === 'Yüksek' ? '#ef4444' : bw.concentration === 'Orta' ? '#f59e0b' : '#22c55e'} />
        <MetricBadge label="Sektör Sayısı"    val={bw.n_sectors} />
      </div>
      <div className="pp-sector-chart">
        {Object.entries(bw.sectors || {}).sort((a, b) => b[1] - a[1]).map(([sec, w]) => (
          <div key={sec} className="pp-sector-row">
            <span className="pp-sector-name">{sec}</span>
            <div className="pp-sector-bar-wrap">
              <div className="pp-sector-bar" style={{width: `${w}%`}} />
            </div>
            <span className="pp-sector-pct">{w.toFixed(1)}%</span>
          </div>
        ))}
      </div>
      <StockTable
        rows={bw.rows}
        cols={[
          { key: 'weight',      label: 'Ağırlık',    fmt: v => v + '%' },
          { key: 'pnl_pct',     label: 'K/Z %',      fmt: v => (v >= 0 ? '+' : '') + v + '%', good: v => v > 5, bad: v => v < -10 },
          { key: 'vol_annual',  label: 'Yıllık Vol %', fmt: v => v != null ? v + '%' : '—', bad: v => v > 50 },
          { key: 'beta',        label: 'Beta',        fmt: v => v != null ? v : '—', good: v => v < 1, bad: v => v > 1.5 },
          { key: 'max_drawdown',label: 'Max DD %',    fmt: v => v != null ? v + '%' : '—', bad: v => v < -30 },
          { key: 'sharpe',      label: 'Sharpe',      fmt: v => v != null ? v : '—', good: v => v > 1, bad: v => v < 0 },
        ]}
      />
    </FwPanel>
  )
}


// ─── JPMorgan — Kazanç ───────────────────────────────────────────────────────
function JpPanel({ data }) {
  const jp = data.jpmorgan_earnings
  const ai = data.ai?.jp
  return (
    <FwPanel icon="💹" title="JPMorgan Chase" subtitle="Equity Research — Kazanç Analizi">
      <AiBox text={ai} firm="JPMorgan" color="#f59e0b" />
      <StockTable
        rows={jp.rows}
        cols={[
          { key: 'weight',     label: 'Ağırlık',   fmt: v => v + '%' },
          { key: 'eps',        label: 'EPS (₺)',   fmt: v => v != null ? '₺' + v : '—', good: v => v > 0, bad: v => v < 0 },
          { key: 'fk',         label: 'F/K',       good: v => v > 0 && v < 20, bad: v => v > 40 },
          { key: 'fk_fwd',     label: 'İleride F/K', good: v => v > 0 && v < 15, bad: v => v > 30 },
          { key: 'kar_buyume', label: 'Kâr Büy %', fmt: v => v != null ? v + '%' : '—', good: v => v > 10, bad: v => v < 0 },
          { key: 'rev_growth', label: 'Gelir Büy %', fmt: v => v != null ? v + '%' : '—', good: v => v > 10, bad: v => v < 0 },
          { key: 'rsi',        label: 'RSI',       good: v => v >= 40 && v <= 60, bad: v => v > 70 },
          { key: 'action',     label: 'Sinyal',    action: true },
        ]}
      />
    </FwPanel>
  )
}


// ─── BlackRock — Temettü ─────────────────────────────────────────────────────
function BlkPanel({ data }) {
  const blk = data.blackrock_dividend
  const ai  = data.ai?.blk
  const fmt = v => '₺' + v.toLocaleString('tr-TR', { minimumFractionDigits: 0 })
  return (
    <FwPanel icon="💰" title="BlackRock" subtitle="Income Strategy — Temettü Geliri Analizi">
      <AiBox text={ai} firm="BlackRock" color="#f59e0b" />
      <div className="pp-metrics-header">
        <MetricBadge label="Yıllık Temettü Geliri" val={fmt(blk.total_income)} color="#22c55e" />
        <MetricBadge label="Port. Temettü Verimi"  val={blk.port_yield + '%'} color={blk.port_yield > 3 ? '#22c55e' : '#94a3b8'} />
      </div>
      <StockTable
        rows={blk.rows}
        cols={[
          { key: 'weight',        label: 'Ağırlık', fmt: v => v + '%' },
          { key: 'value',         label: 'Değer',   fmt: v => '₺' + v.toLocaleString('tr-TR', {minimumFractionDigits:0}) },
          { key: 'yield_pct',     label: 'Temettü %', fmt: v => v ? v + '%' : '—', good: v => v > 3 },
          { key: 'annual_income', label: 'Yıllık Gelir', fmt: v => '₺' + v.toLocaleString('tr-TR', {minimumFractionDigits:0}), good: v => v > 1000 },
        ]}
      />
      <div className="pp-projection-title">📅 10 Yıllık Temettü Geliri Projeksiyonu (%5 yıllık büyüme)</div>
      <div className="pp-projection-grid">
        {blk.projection.map(p => (
          <div key={p.year} className="pp-proj-cell">
            <span className="pp-proj-yr">{p.year}. yıl</span>
            <span className="pp-proj-val">₺{p.income.toLocaleString('tr-TR', {minimumFractionDigits:0})}</span>
          </div>
        ))}
      </div>
    </FwPanel>
  )
}


// ─── Citadel — Sektör ────────────────────────────────────────────────────────
function CitPanel({ data }) {
  const cit = data.citadel_sector
  const ai  = data.ai?.cit
  const COLORS = ['#3b82f6','#10b981','#f59e0b','#a78bfa','#ef4444','#06b6d4','#ec4899','#84cc16']
  return (
    <FwPanel icon="🌐" title="Citadel" subtitle="Macro Strategy — Sektör Dağılımı & Rotasyon">
      <AiBox text={ai} firm="Citadel" color="#06b6d4" />
      <div className="pp-metrics-header">
        <MetricBadge label="Sektör Konsantrasyonu" val={cit.concentration} color={cit.concentration === 'Yüksek' ? '#ef4444' : cit.concentration === 'Orta' ? '#f59e0b' : '#22c55e'} />
        <MetricBadge label="HHI Endeksi" val={cit.hhi} />
        <MetricBadge label="Sektör Sayısı" val={cit.n_sectors} />
      </div>
      <div className="pp-sector-donut">
        {cit.rows.map((r, i) => (
          <div key={r.sector} className="pp-cit-sector-row">
            <div className="pp-cit-color" style={{background: COLORS[i % COLORS.length]}} />
            <span className="pp-cit-name">{r.sector}</span>
            <span className="pp-cit-tickers">{r.tickers.join(', ')}</span>
            <div className="pp-cit-bar-wrap">
              <div className="pp-cit-bar" style={{width: `${r.weight}%`, background: COLORS[i % COLORS.length]}} />
            </div>
            <span className="pp-cit-pct">{r.weight.toFixed(1)}%</span>
            <span className="pp-cit-score" style={{color: r.avg_score >= 6 ? '#22c55e' : r.avg_score >= 4.5 ? '#f59e0b' : '#ef4444'}}>
              {r.avg_score}/10
            </span>
          </div>
        ))}
      </div>
    </FwPanel>
  )
}


// ─── Renaissance — Kantitatif ────────────────────────────────────────────────
function RenPanel({ data }) {
  const ren = data.renaissance_quant
  const ai  = data.ai?.ren
  return (
    <FwPanel icon="🔬" title="Renaissance Technologies" subtitle="Quant Research — Çok Faktörlü Tarama">
      <AiBox text={ai} firm="Renaissance" color="#a78bfa" />
      <div className="pp-ren-legend">
        <span className="pp-ren-leg-item"><span style={{color:'#3b82f6'}}>■</span> Değer (25p)</span>
        <span className="pp-ren-leg-item"><span style={{color:'#10b981'}}>■</span> Kalite (25p)</span>
        <span className="pp-ren-leg-item"><span style={{color:'#f59e0b'}}>■</span> Momentum (25p)</span>
        <span className="pp-ren-leg-item"><span style={{color:'#a78bfa'}}>■</span> Büyüme (25p)</span>
      </div>
      {ren.rows.map((r, i) => (
        <div key={r.ticker} className="pp-ren-row">
          <div className="pp-ren-rank">#{i + 1}</div>
          <div className="pp-ren-ticker pp-ticker-btn" onClick={() => onTickerClick?.(r.ticker)}>{r.ticker}</div>
          <div className="pp-ren-bars">
            <FactorBar val={r.val_score}  max={25} color="#3b82f6" label="Değer" />
            <FactorBar val={r.qual_score} max={25} color="#10b981" label="Kalite" />
            <FactorBar val={r.mom_score}  max={25} color="#f59e0b" label="Momentum" />
            <FactorBar val={r.grow_score} max={25} color="#a78bfa" label="Büyüme" />
          </div>
          <div className="pp-ren-composite" style={{color: r.composite >= 7 ? '#f59e0b' : r.composite >= 5 ? '#22c55e' : '#ef4444'}}>
            {r.composite}<span style={{fontSize:10,color:'#64748b'}}>/10</span>
          </div>
          <ActionBadge action={r.action} />
        </div>
      ))}
    </FwPanel>
  )
}


// ─── Two Sigma — Makro ───────────────────────────────────────────────────────
function TwoSigmaPanel({ data }) {
  const ai = data.ai?.two_sigma
  const raw = data.raw
  const stocks = Object.values(raw?.stocks || {})
  const bullCount = stocks.filter(s => s.analysis?.weekly_bias === 'Yükseliş').length
  const avgScore  = stocks.length ? (stocks.reduce((s, v) => s + (v.analysis?.ai_score || 0), 0) / stocks.length).toFixed(1) : 0

  return (
    <FwPanel icon="🌍" title="Two Sigma" subtitle="Macro Strategy — Piyasa Görünümü">
      <AiBox text={ai} firm="Two Sigma" color="#38bdf8" />
      <div className="pp-metrics-header">
        <MetricBadge label="Haftalık Yükseliş" val={`${bullCount}/${stocks.length}`} color={bullCount > stocks.length/2 ? '#22c55e' : '#ef4444'} />
        <MetricBadge label="Ort. AI Skoru"      val={avgScore + '/10'} color={avgScore >= 6 ? '#22c55e' : avgScore >= 4.5 ? '#f59e0b' : '#ef4444'} />
      </div>
      <div className="pp-macro-grid">
        <MacroCard title="BIST Momentum" val={bullCount > stocks.length/2 ? 'POZİTİF' : 'NEGATİF'} color={bullCount > stocks.length/2 ? '#22c55e' : '#ef4444'} desc="Portföydeki hisselerin haftalık bias dağılımı" />
        <MacroCard title="TL Kur Riski" val="YÜKSEK" color="#ef4444" desc="TCMB politikası ve küresel risk iştahı izlenmeli" />
        <MacroCard title="Enflasyon Etkisi" val="NÖTR" color="#f59e0b" desc="Yüksek enflasyon nominal büyümeyi destekliyor" />
        <MacroCard title="Portföy Pozisyonu" val={avgScore >= 6 ? 'AĞIRLIK ARTIR' : avgScore >= 4.5 ? 'TUT' : 'AZALT'} color={avgScore >= 6 ? '#22c55e' : avgScore >= 4.5 ? '#f59e0b' : '#ef4444'} desc="AI skor ortalamasına göre tavsiye" />
      </div>
    </FwPanel>
  )
}


// ─── Yardımcı Bileşenler ─────────────────────────────────────────────────────

function FwPanel({ icon, title, subtitle, children }) {
  return (
    <div className="pp-fw-panel">
      <div className="pp-fw-panel-hdr">
        <span className="pp-fw-panel-icon">{icon}</span>
        <div>
          <div className="pp-fw-panel-title">{title}</div>
          <div className="pp-fw-panel-sub">{subtitle}</div>
        </div>
      </div>
      {children}
    </div>
  )
}

function AiBox({ text, firm, color, note }) {
  if (note && !text) return (
    <div className="pp-ai-note">{note}</div>
  )
  if (!text) return null
  return (
    <div className="pp-ai-box" style={{borderLeftColor: color}}>
      <div className="pp-ai-box-hdr" style={{color}}>◈ {firm} AI Notu</div>
      <div className="pp-ai-box-text">{text}</div>
    </div>
  )
}

function MetricBadge({ label, val, color, good, bad }) {
  const v = val != null ? val : '—'
  const n = parseFloat(v)
  let c = color || '#94a3b8'
  if (!color) {
    if (good && !isNaN(n) && good(n)) c = '#22c55e'
    else if (bad && !isNaN(n) && bad(n)) c = '#ef4444'
  }
  return (
    <div className="pp-metric-badge">
      <span className="pp-metric-lbl">{label}</span>
      <span className="pp-metric-val" style={{color: c}}>{v}</span>
    </div>
  )
}

function SumCard({ label, val, color }) {
  return (
    <div className="pp-sum-card">
      <span className="pp-sum-lbl">{label}</span>
      <span className="pp-sum-val" style={color ? {color} : {}}>{val}</span>
    </div>
  )
}

function ActionBadge({ action }) {
  const cls = action === 'GÜÇLÜ AL' ? 'ab-strong'
    : action === 'AL'  ? 'ab-buy'
    : action === 'İZLE' ? 'ab-watch'
    : action === 'ZAYIF' ? 'ab-weak'
    : 'ab-sell'
  return <span className={`pp-action-badge ${cls}`}>{action || '—'}</span>
}

function FactorBar({ val, max, color, label }) {
  const pct = Math.round((val / max) * 100)
  return (
    <div className="pp-factor-bar-wrap" title={`${label}: ${val}/${max}`}>
      <div className="pp-factor-bar" style={{width: `${pct}%`, background: color}} />
    </div>
  )
}

function MacroCard({ title, val, color, desc }) {
  return (
    <div className="pp-macro-card">
      <div className="pp-macro-title">{title}</div>
      <div className="pp-macro-val" style={{color}}>{val}</div>
      <div className="pp-macro-desc">{desc}</div>
    </div>
  )
}

function StockTable({ rows, cols }) {
  function cellColor(col, raw) {
    if (raw == null) return '#64748b'
    const n = parseFloat(raw)
    if (!isNaN(n)) {
      if (col.good && col.good(n)) return '#4ade80'
      if (col.bad  && col.bad(n))  return '#f87171'
    }
    return '#e2e8f0'
  }

  return (
    <div className="pp-stock-table-wrap">
      <table className="pp-stock-table">
        <thead>
          <tr>
            <th>Hisse</th>
            {cols.map(c => <th key={c.key}>{c.label}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map(r => (
            <tr key={r.ticker}>
              <td className="pp-stock-ticker pp-ticker-btn" onClick={() => onTickerClick?.(r.ticker)}>{r.ticker}</td>
              {cols.map(col => {
                const raw = r[col.key]
                if (col.action) return <td key={col.key}><ActionBadge action={raw} /></td>
                if (col.trend) return <td key={col.key} style={{color: raw === 'BOĞA' ? '#4ade80' : '#f87171'}}>{raw === 'BOĞA' ? '🐂 Yükseliş' : '🐻 Düşüş'}</td>
                if (col.structure) return <td key={col.key} style={{color: raw === 'YUKSELIS' ? '#4ade80' : raw === 'DUSUS' ? '#f87171' : '#94a3b8'}}>{raw === 'YUKSELIS' ? '⬆ HH+HL' : raw === 'DUSUS' ? '⬇ LH+LL' : '↔ Yatay'}</td>
                if (col.bias) return <td key={col.key} style={{color: raw === 'Yükseliş' ? '#4ade80' : raw === 'Düşüş' ? '#f87171' : '#94a3b8'}}>{raw || '—'}</td>
                const display = col.fmt ? col.fmt(raw) : (raw != null ? raw : '—')
                return (
                  <td key={col.key} style={{color: cellColor(col, raw)}}>{display}</td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
