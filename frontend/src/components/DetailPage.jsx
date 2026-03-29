import { useState } from 'react'
import './DetailPage.css'
import PatternChart from './PatternChart'
const TV = 'https://www.tradingview.com/chart/?symbol=BIST:'

function mdToHtml(text) {
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    // Tables
    .replace(/^\|(.+)\|$/gm, (_, row) => {
      const cells = row.split('|').map(c => c.trim())
      const isHeader = false
      return '<tr>' + cells.map(c => `<td>${c}</td>`).join('') + '</tr>'
    })
    .replace(/(<tr>.*<\/tr>\n?)+/gs, m => `<table>${m}</table>`)
    // Headers
    .replace(/^### (.+)$/gm, '<h4>$1</h4>')
    .replace(/^## (.+)$/gm,  '<h3>$1</h3>')
    .replace(/^# (.+)$/gm,   '<h2>$1</h2>')
    // Bold
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    // Horizontal rule
    .replace(/^---$/gm, '<hr/>')
    // Line breaks → paragraphs
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br/>')
    .replace(/^(.+)$/, '<p>$1</p>')
}

const TF_LABELS = { tf_4h: '4 Saatlik', tf_1d: 'Günlük', tf_1w: 'Haftalık' }
const TF_KEYS   = ['tf_4h', 'tf_1d', 'tf_1w']

const AI_FIRMS = [
  { key: 'gs_stock',         icon: '🏦', label: 'Goldman Sachs', sub: 'Temel Analiz' },
  { key: 'ms_stock',         icon: '📈', label: 'Morgan Stanley', sub: 'Teknik Analiz' },
  { key: 'bw_stock',         icon: '🛡',  label: 'Bridgewater',   sub: 'Risk' },
  { key: 'two_sigma_stock',  icon: '🌍', label: 'Two Sigma',      sub: 'Makro' },
]

export default function DetailPage({ stock, onClose }) {
  const [activeTf, setActiveTf]     = useState('tf_1d')
  const [activeView, setActiveView] = useState('teknik')   // 'teknik' | 'kurumsal' | 'equity'
  const [deepData, setDeepData]     = useState(null)
  const [deepLoading, setDeepLoading] = useState(false)
  const [activeFirm, setActiveFirm] = useState('gs_stock')
  const [equityData, setEquityData]   = useState(null)
  const [equityLoading, setEquityLoading] = useState(false)

  if (!stock) return null
  const tf = stock[activeTf]
  const { ticker, price, change_pct, ai_score, ai_action, bullets, stats, weekly_bias, fundamentals, fund_score, fund_verdict, fund_reasons, whale, news, insider } = stock

  const pos = change_pct >= 0
  const scoreColor = ai_score >= 7.5 ? '#f59e0b' : ai_score >= 6 ? '#22c55e' : ai_score >= 4.5 ? '#60a5fa' : '#ef4444'
  const actCls = ai_action === 'GÜÇLÜ AL' ? 'act-strong' : ai_action === 'AL' ? 'act-buy' : ai_action === 'İZLE' ? 'act-watch' : ai_action === 'ZAYIF' ? 'act-weak' : 'act-sell'

  async function loadDeepAnalysis() {
    if (deepData) { setActiveView('kurumsal'); return }
    setDeepLoading(true)
    setActiveView('kurumsal')
    try {
      const res  = await fetch(`/api/stock/${ticker}/deep-analysis`)
      const data = await res.json()
      setDeepData(data)
    } catch(e) { setDeepData({ error: e.message }) }
    finally { setDeepLoading(false) }
  }

  async function loadEquityResearch() {
    if (equityData) { setActiveView('equity'); return }
    setEquityLoading(true)
    setActiveView('equity')
    try {
      const res  = await fetch(`/api/stock/${ticker}/equity-research`)
      const data = await res.json()
      setEquityData(data)
    } catch(e) { setEquityData({ error: e.message }) }
    finally { setEquityLoading(false) }
  }

  return (
    <div className="dp-overlay" onClick={onClose}>
      <div className="dp-panel" onClick={e => e.stopPropagation()}>

        {/* ── Panel Header ── */}
        <div className="dp-hdr">
          <div className="dp-title">
            <span className="dp-ticker">{ticker}</span>
            <span className="dp-price">₺{price?.toLocaleString('tr-TR',{minimumFractionDigits:1,maximumFractionDigits:2})}</span>
            <span className={`dp-chg ${pos?'pos':'neg'}`}>{pos?'+':''}{change_pct?.toFixed(2)}%</span>
            <span className="dp-badge" style={{color:scoreColor,borderColor:scoreColor}}>Skor: {ai_score}/10</span>
          </div>
          <div className="dp-hdr-right">
            <a href={`${TV}${ticker}`} target="_blank" rel="noopener noreferrer" className="dp-tv-btn">
              ⬡ TradingView
            </a>
            <button className="dp-close" onClick={onClose}>✕</button>
          </div>
        </div>

        {/* ── Görünüm Seçici + TF Sekmeler ── */}
        <div className="dp-tabs">
          <button
            className={`dp-view-btn ${activeView === 'teknik' ? 'dp-view-active' : ''}`}
            onClick={() => setActiveView('teknik')}
          >📊 Teknik</button>
          <button
            className={`dp-view-btn ${activeView === 'kurumsal' ? 'dp-view-active' : ''}`}
            onClick={loadDeepAnalysis}
          >
            {deepLoading ? '⟳ Yükleniyor…' : '🏦 Kurumsal AI'}
          </button>
          <button
            className={`dp-view-btn dp-view-equity ${activeView === 'equity' ? 'dp-view-active' : ''}`}
            onClick={loadEquityResearch}
          >
            {equityLoading ? '⟳ Yükleniyor…' : '📋 Equity Research'}
          </button>
          <div className="dp-tabs-divider" />
          {activeView === 'teknik' && TF_KEYS.map(k => (
            <button key={k}
              className={`dp-tab ${activeTf === k ? 'dp-tab-active' : ''} ${!stock[k] ? 'dp-tab-disabled' : ''}`}
              onClick={() => stock[k] && setActiveTf(k)}
            >{TF_LABELS[k]}{!stock[k] ? ' (yok)' : ''}</button>
          ))}
          {activeView === 'kurumsal' && AI_FIRMS.map(f => (
            <button key={f.key}
              className={`dp-tab ${activeFirm === f.key ? 'dp-tab-active' : ''}`}
              onClick={() => setActiveFirm(f.key)}
            >{f.icon} {f.label}</button>
          ))}
        </div>

        {/* ── Kurumsal AI Görünümü ── */}
        {activeView === 'kurumsal' && (
          <div className="dp-body">
            {deepLoading && (
              <div className="dp-deep-loading">
                <div className="dp-deep-spin">⟳</div>
                <div>Goldman Sachs • Morgan Stanley • Bridgewater • Two Sigma</div>
                <div style={{fontSize:11,color:'#475569',marginTop:6}}>AI analizleri paralel üretiliyor (~10-15 sn)…</div>
              </div>
            )}
            {deepData?.error && <div className="dp-no-tf">{deepData.error}</div>}
            {deepData && !deepData.error && !deepLoading && (() => {
              const ai = deepData.ai_analysis || {}
              const firm = AI_FIRMS.find(f => f.key === activeFirm)
              const text = ai[activeFirm]
              return (
                <div className="dp-deep-panel">
                  <div className="dp-deep-hdr">
                    <span className="dp-deep-icon">{firm?.icon}</span>
                    <div>
                      <div className="dp-deep-firm">{firm?.label}</div>
                      <div className="dp-deep-sub">{firm?.sub} Raporu — {ticker}</div>
                    </div>
                  </div>
                  {text
                    ? <div className="dp-deep-text" dangerouslySetInnerHTML={{__html: mdToHtml(text)}} />
                    : <div className="dp-no-tf">Bu framework için analiz alınamadı.</div>
                  }
                </div>
              )
            })()}
          </div>
        )}

        {/* ── Equity Research Görünümü ── */}
        {activeView === 'equity' && (
          <div className="dp-body">
            {equityLoading && (
              <div className="dp-deep-loading">
                <div className="dp-deep-spin">⟳</div>
                <div>Equity Research Raporu Hazırlanıyor</div>
                <div style={{fontSize:11,color:'#475569',marginTop:6}}>Claude AI profesyonel analiz üretiyor (~15-20 sn)…</div>
              </div>
            )}
            {equityData?.error && <div className="dp-no-tf">{equityData.error}</div>}
            {equityData && !equityData.error && !equityLoading && (
              <div className="dp-equity-panel">
                <div className="dp-equity-hdr">
                  <div className="dp-equity-meta">
                    <span className="dp-equity-ticker">{equityData.ticker}</span>
                    <span className="dp-equity-price">₺{equityData.price?.toLocaleString('tr-TR',{minimumFractionDigits:1,maximumFractionDigits:2})}</span>
                    <span className={`dp-equity-action act-${equityData.action === 'GÜÇLÜ AL' ? 'strong' : equityData.action === 'AL' ? 'buy' : equityData.action === 'İZLE' ? 'watch' : 'sell'}`}>
                      {equityData.action}
                    </span>
                    <span className="dp-equity-score">Skor: {equityData.score}/10</span>
                  </div>
                  <div className="dp-equity-badge">📋 Equity Research Raporu</div>
                </div>
                <div className="dp-equity-report" dangerouslySetInnerHTML={{__html: mdToHtml(equityData.report || '')}} />
                <button className="dp-equity-refresh" onClick={() => { setEquityData(null); loadEquityResearch() }}>
                  ↺ Raporu Yenile
                </button>
              </div>
            )}
          </div>
        )}

        {activeView === 'teknik' && !tf ? (
          <div className="dp-no-tf">Bu zaman dilimi için yeterli veri yok.</div>
        ) : activeView === 'teknik' ? (
          <div className="dp-body">

            {/* ── Mum Grafik ── */}
            {(() => {
              const chartLevels = []
              if (tf?.ma20)   chartLevels.push({ price: tf.ma20,   color: '#f59e0b', label: 'HO20', dash: true })
              if (tf?.ema200) chartLevels.push({ price: tf.ema200, color: '#f97316', label: 'EMA200', dash: true })
              if (tf?.sl)     chartLevels.push({ price: tf.sl,     color: '#ef4444', label: 'ZK',    dash: false })
              if (tf?.tp1)    chartLevels.push({ price: tf.tp1,    color: '#22c55e', label: 'H1',    dash: false })
              if (tf?.tp2)    chartLevels.push({ price: tf.tp2,    color: '#4ade80', label: 'H2',    dash: false })
              ;(tf?.supports    || []).slice(0, 1).forEach(s =>
                chartLevels.push({ price: s, color: '#22c55e88', label: 'Des', dash: true }))
              ;(tf?.resistances || []).slice(0, 1).forEach(r =>
                chartLevels.push({ price: r, color: '#ef444488', label: 'Dir', dash: true }))
              const TF_INTERVAL = { tf_4h: '4h', tf_1d: '1d', tf_1w: '1wk' }
              const TF_DAYS     = { tf_4h: 30,   tf_1d: 180,  tf_1w: 365  }
              return (
                <PatternChart
                  ticker={ticker}
                  patterns={[]}
                  price={price}
                  levels={chartLevels}
                  interval={TF_INTERVAL[activeTf] || '1d'}
                  days={TF_DAYS[activeTf] || 180}
                />
              )
            })()}

            <div className="dp-cols">

              {/* SOL ── Piyasa Yapısı + Trend */}
              <div className="dp-col">

                {/* Piyasa Yapısı */}
                <Section title="📐 Piyasa Yapısı">
                  <Row label="Yapı" val={
                    tf.market_structure === 'YUKSELIS' ? '⬆ Yükseliş (HH+HL)' :
                    tf.market_structure === 'DUSUS'    ? '⬇ Düşüş (LH+LL)' : '↔ Yatay Bant'
                  } color={tf.market_structure==='YUKSELIS'?'#22c55e':tf.market_structure==='DUSUS'?'#ef4444':'#94a3b8'} />
                  {tf.hh && <Row label="Son Yüksek Tepe (HH)" val={`₺${tf.hh}`} color="#22c55e"/>}
                  {tf.hl && <Row label="Son Yüksek Dip (HL)"  val={`₺${tf.hl}`} color="#22c55e"/>}
                  {tf.lh && <Row label="Son Alçak Tepe (LH)"  val={`₺${tf.lh}`} color="#ef4444"/>}
                  {tf.ll && <Row label="Son Alçak Dip (LL)"   val={`₺${tf.ll}`} color="#ef4444"/>}
                  {tf.bos && <Row label="Yapı Kırılımı (BOS)" val={tf.bos} color="#a78bfa"/>}
                </Section>

                {/* Trend */}
                <Section title="📈 Trend Analizi">
                  <Row label="Trend"   val={tf.trend==='BOĞA'?'🐂 Yükseliş':'🐻 Düşüş'} color={tf.trend==='BOĞA'?'#22c55e':'#ef4444'}/>
                  <Row label="HO 20"   val={`₺${tf.ma20}`}  color={price > tf.ma20  ? '#22c55e' : '#ef4444'}/>
                  <Row label="HO 8"    val={`₺${tf.ma8}`}   color={price > tf.ma8   ? '#22c55e' : '#ef4444'}/>
                  {tf.ema200 && <Row label="EMA 200" val={`₺${tf.ema200}`} color={price > tf.ema200 ? '#22c55e' : '#ef4444'}/>}
                  <Row label="Bölge" val={tf.price_zone === 'PAHALI' ? '🔴 Premium (Pahalı)' : '🟢 Discount (Ucuz)'}
                    color={tf.price_zone === 'PAHALI' ? '#f87171' : '#4ade80'}/>
                </Section>

                {/* Göstergeler */}
                <Section title="📊 Göstergeler">
                  <Row label="RSI (14)" val={`${tf.rsi}  →  ${tf.rsi_state}`}
                    color={tf.rsi>70?'#ef4444':tf.rsi<30?'#22c55e':'#38bdf8'}/>
                  {tf.macd && (
                    <Row label={`MACD ${tf.macd.type}`} val={`${tf.macd.value}  (${tf.macd.date})`}
                      color={tf.macd.bullish?'#22c55e':'#ef4444'}/>
                  )}
                  <Row label="ATR (14)"      val={`₺${tf.atr}`} color="#94a3b8"/>
                  <Row label="Relatif Hacim" val={`${tf.rel_vol}x`}
                    color={tf.rel_vol>1.5?'#22c55e':tf.rel_vol<0.7?'#ef4444':'#94a3b8'}/>
                </Section>

                {/* Mum Formasyonları */}
                <Section title="🕯 Mum Formasyonları">
                  {tf.candle_patterns?.length > 0 ? tf.candle_patterns.map((p,i) => (
                    <Row key={i} label={p.date} val={p.ad}
                      color={p.bull===true?'#22c55e':p.bull===false?'#ef4444':'#94a3b8'}/>
                  )) : <span className="dp-empty">Son dönemde öne çıkan formasyon yok.</span>}
                </Section>
              </div>

              {/* SAĞ ── SMC + İşlem Planı */}
              <div className="dp-col">

                {/* Destek & Direnç */}
                <Section title="🧱 Destek & Direnç Seviyeleri">
                  {tf.resistances?.length > 0 && (
                    <div>
                      <span className="dp-sub-lbl">📛 Direnç</span>
                      {tf.resistances.slice(0,3).map((r,i)=>(
                        <Row key={i} label={`D${i+1}`} val={`₺${r}`} color="#ef4444"/>
                      ))}
                    </div>
                  )}
                  <Row label="— MEVCUT FİYAT —" val={`₺${price}`} color="#38bdf8"/>
                  {tf.supports?.length > 0 && (
                    <div>
                      <span className="dp-sub-lbl">🛡 Destek</span>
                      {tf.supports.slice(0,3).map((s,i)=>(
                        <Row key={i} label={`S${i+1}`} val={`₺${s}`} color="#22c55e"/>
                      ))}
                    </div>
                  )}
                </Section>

                {/* Arz & Talep / SMC — Multiple OBs */}
                <Section title="🟩 Arz & Talep Bölgeleri (Order Blocks)">
                  {/* Demand zones (Bullish OBs) */}
                  {tf.bull_obs?.length > 0 ? (
                    <>
                      <span className="dp-sub-lbl" style={{color:'#4ade80'}}>🟢 Talep Bölgeleri (Demand / Bullish OB)</span>
                      {tf.bull_obs.map((ob, i) => (
                        <div key={i} className={`dp-ob bull-ob-box ${ob.tested ? 'ob-tested' : ''}`} style={{marginTop:4}}>
                          <div style={{display:'flex',alignItems:'center',justifyContent:'space-between'}}>
                            <span className="dp-ob-title">Talep #{i+1} — {ob.date}</span>
                            {ob.tested && <span style={{fontSize:10,color:'#f59e0b',fontWeight:700}}>⚡ Test Ediliyor</span>}
                          </div>
                          <Row label="Bölge Üst" val={`₺${ob.high}`}  color="#86efac"/>
                          <Row label="Bölge Alt" val={`₺${ob.low}`}   color="#86efac"/>
                          <Row label="Güç"       val={`${ob.strength}%`} color="#4ade80"/>
                        </div>
                      ))}
                    </>
                  ) : <span className="dp-empty">Aktif Bullish OB yok.</span>}

                  {/* Supply zones (Bearish OBs) */}
                  {tf.bear_obs?.length > 0 && (
                    <>
                      <span className="dp-sub-lbl" style={{color:'#f87171',marginTop:8,display:'block'}}>🔴 Arz Bölgeleri (Supply / Bearish OB)</span>
                      {tf.bear_obs.map((ob, i) => (
                        <div key={i} className={`dp-ob bear-ob-box ${ob.tested ? 'ob-tested' : ''}`} style={{marginTop:4}}>
                          <div style={{display:'flex',alignItems:'center',justifyContent:'space-between'}}>
                            <span className="dp-ob-title" style={{color:'#f87171'}}>Arz #{i+1} — {ob.date}</span>
                            {ob.tested && <span style={{fontSize:10,color:'#f59e0b',fontWeight:700}}>⚡ Test Ediliyor</span>}
                          </div>
                          <Row label="Bölge Üst" val={`₺${ob.high}`}  color="#fca5a5"/>
                          <Row label="Bölge Alt" val={`₺${ob.low}`}   color="#fca5a5"/>
                          <Row label="Güç"       val={`${ob.strength}%`} color="#f87171"/>
                        </div>
                      ))}
                    </>
                  )}

                  {/* Fair Value Gap */}
                  {tf.bull_fvg && (
                    <div className="dp-ob fvg-box" style={{marginTop:6}}>
                      <span className="dp-ob-title" style={{color:'#67e8f9'}}>Bullish Fair Value Gap</span>
                      <Row label="FVG Üst" val={`₺${tf.bull_fvg.high}`} color="#67e8f9"/>
                      <Row label="FVG Alt" val={`₺${tf.bull_fvg.low}`}  color="#67e8f9"/>
                      <Row label="Tarih"   val={tf.bull_fvg.date}        color="#475569"/>
                    </div>
                  )}
                  {tf.liq_sweep && (
                    <div className="dp-ob sweep-box" style={{marginTop:6}}>
                      <span className="dp-ob-title" style={{color:'#a78bfa'}}>🧹 {tf.liq_sweep.type}</span>
                      <Row label="Seviye" val={`₺${tf.liq_sweep.price}`} color="#a78bfa"/>
                      <Row label="Tarih"  val={tf.liq_sweep.date}          color="#475569"/>
                    </div>
                  )}
                </Section>

                {/* Fibonacci Seviyeleri */}
                {tf.fibonacci && (
                  <Section title="📐 Fibonacci Seviyeleri">
                    <div className="dp-fib-header">
                      <span className="dp-fib-swing">
                        {tf.fibonacci.trend === 'up' ? '⬆ Yükseliş' : '⬇ Retracement'} —
                        Tepe: ₺{tf.fibonacci.swing_high} ({tf.fibonacci.sh_date}) /
                        Dip: ₺{tf.fibonacci.swing_low} ({tf.fibonacci.sl_date})
                      </span>
                      <span className="dp-fib-nearest">
                        Yakın Seviye: <b>{tf.fibonacci.nearest_level}</b> (₺{tf.fibonacci.nearest_price})
                      </span>
                    </div>
                    <div className="dp-fib-grid">
                      {Object.entries(tf.fibonacci.retracement).map(([ratio, lvlPrice]) => {
                        const isNearest = ratio === tf.fibonacci.nearest_level
                        const abovePrice = lvlPrice > price
                        const keyFib = ['0.382','0.500','0.618'].includes(ratio)
                        return (
                          <div key={ratio} className={`dp-fib-row ${isNearest ? 'fib-nearest' : ''} ${keyFib ? 'fib-key' : ''}`}>
                            <span className="dp-fib-ratio">{ratio}</span>
                            <div className="dp-fib-bar-wrap">
                              <div className="dp-fib-bar" style={{
                                width: `${Math.min(100, Math.abs(lvlPrice - price) / (tf.fibonacci.swing_high - tf.fibonacci.swing_low) * 100 * 2)}%`,
                                background: abovePrice ? '#ef4444' : '#22c55e',
                                opacity: 0.4,
                              }}/>
                            </div>
                            <span className="dp-fib-price" style={{color: abovePrice ? '#f87171' : '#4ade80'}}>
                              ₺{lvlPrice}
                            </span>
                            <span className="dp-fib-dist" style={{color: abovePrice ? '#ef4444' : '#22c55e'}}>
                              {abovePrice ? '▲' : '▼'} {Math.abs(((lvlPrice-price)/price)*100).toFixed(1)}%
                            </span>
                          </div>
                        )
                      })}
                    </div>
                    <div className="dp-fib-ext-title">Uzantı Seviyeleri</div>
                    <div className="dp-fib-grid">
                      {Object.entries(tf.fibonacci.extension).map(([ratio, lvlPrice]) => {
                        const abovePrice = lvlPrice > price
                        return (
                          <div key={ratio} className="dp-fib-row fib-ext">
                            <span className="dp-fib-ratio">{ratio}</span>
                            <div className="dp-fib-bar-wrap" />
                            <span className="dp-fib-price" style={{color:'#a78bfa'}}>₺{lvlPrice}</span>
                            <span className="dp-fib-dist" style={{color:'#7c3aed'}}>
                              {abovePrice ? '▲' : '▼'} {Math.abs(((lvlPrice-price)/price)*100).toFixed(1)}%
                            </span>
                          </div>
                        )
                      })}
                    </div>
                  </Section>
                )}

                {/* Hacim Analizi */}
                <Section title="📦 Hacim Analizi">
                  <Row label="Durum"        val={tf.vol_state}   color={tf.vol_state==='YUKSEK'?'#22c55e':tf.vol_state==='KLİMAX'?'#f59e0b':'#94a3b8'}/>
                  <Row label="Yorum"         val={tf.vol_desc}   color="#64748b"/>
                </Section>

                {/* İşlem Planı */}
                <Section title="🎯 İşlem Planı (Spot)">
                  <Row label="📍 Mevcut Fiyat" val={`₺${price}`}   color="#38bdf8"/>
                  <Row label="🛑 Zarar Kes (ZK)" val={`₺${tf.sl}`} color="#ef4444"/>
                  <Row label="🎯 Hedef 1 (H1)"  val={`₺${tf.tp1}`} color="#22c55e"/>
                  <Row label="🏆 Hedef 2 (H2)"  val={`₺${tf.tp2}`} color="#10b981"/>
                  <Row label="⚠️ Risk"           val={`%${tf.risk_pct} sermaye`} color="#f59e0b"/>
                  <Row label="⚖️ Risk:Ödül"      val={`1 : ${tf.rr}`}           color="#a78bfa"/>
                  <div className="dp-note">
                    {tf.rr >= 2
                      ? '✓ Kabul edilebilir R:R — minimum 1:2 sağlandı'
                      : '⚠ R:R yetersiz — daha iyi giriş noktası bekle'}
                  </div>
                </Section>

                {/* AI Gerekçeleri */}
                <Section title="🧠 AI Skor Gerekçeleri">
                  {tf.reasons?.map((r,i) => (
                    <div key={i} className="dp-reason">{r}</div>
                  ))}
                </Section>
              </div>
            </div>

            {/* ── Alt — İstatistik + Genel AI + Temel Analiz ── */}
            <div className="dp-footer">

              {/* İstatistik + AI yan yana */}
              <div className="dp-footer-row">
                {stats && (
                  <div className="dp-stat-box">
                    <span className="dp-stat-title">📅 Geçmiş Veriden İstatistik</span>
                    <div className="dp-stat-grid">
                      <div>
                        <span className="dp-stat-lbl">En Hareketli Günler</span>
                        <span className="dp-stat-val">{stats.best_days?.join(' • ')}</span>
                      </div>
                      <div>
                        <span className="dp-stat-lbl">En Aktif Saatler</span>
                        <span className="dp-stat-val">{stats.best_hours?.join(' • ')}</span>
                      </div>
                      <div>
                        <span className="dp-stat-lbl">Ort. Günlük Hareket</span>
                        <span className="dp-stat-val">%{stats.avg_daily_range_pct}</span>
                      </div>
                      <div>
                        <span className="dp-stat-lbl">Haftalık Bias</span>
                        <span className="dp-stat-val" style={{color: weekly_bias==='Yükseliş'?'#22c55e':weekly_bias==='Düşüş'?'#ef4444':'#94a3b8'}}>{weekly_bias}</span>
                      </div>
                    </div>
                  </div>
                )}

                {/* Genel AI */}
                <div className="dp-ai-final">
                  <div className="dp-ai-hdr">
                    <span>◈ THS AI — Genel Değerlendirme</span>
                    <span className="dp-ai-score" style={{color:scoreColor}}>{ai_score} / 10</span>
                  </div>
                  <button className={`dp-act-btn ${actCls}`}>{ai_action}</button>
                  {bullets?.map((b,i) => <div key={i} className="dp-bullet">• {b}</div>)}
                </div>
              </div>{/* /dp-footer-row */}

              {/* Temel Analiz — tam genişlik */}
              {fundamentals && Object.keys(fundamentals).length > 0 && (
                <div className="dp-fund-box">
                  <span className="dp-stat-title">📋 Temel Analiz</span>
                  {(fundamentals.sektor || fundamentals.endustri) && (
                    <div className="dp-fund-sector">
                      {fundamentals.sektor && <span className="dp-fund-sector-tag">{fundamentals.sektor}</span>}
                      {fundamentals.endustri && <span className="dp-fund-sector-tag" style={{color:'#94a3b8'}}>{fundamentals.endustri}</span>}
                    </div>
                  )}
                  {/* Temel Skor */}
                  {fund_score != null && (
                    <div className="dp-fund-score-row">
                      <span className="dp-fund-score-lbl">Temel Analiz Skoru</span>
                      <span className="dp-fund-score-val" style={{color: fund_score>=7?'#f59e0b':fund_score>=5?'#22c55e':fund_score>=3?'#60a5fa':'#ef4444'}}>
                        {fund_score} / 10
                      </span>
                      <span className="dp-fund-verdict">{fund_verdict}</span>
                    </div>
                  )}
                  {fund_reasons?.length > 0 && (
                    <div className="dp-fund-reasons">
                      {fund_reasons.map((r,i) => <span key={i} className="dp-fund-reason">{r}</span>)}
                    </div>
                  )}

                  <div className="dp-fund-grid">
                    <FundCell label="F/K (P/E)" val={fundamentals.fk} good={v => v > 0 && v < 20} bad={v => v > 40 || v < 0} />
                    <FundCell label="İleride F/K" val={fundamentals.fk_forward} good={v => v > 0 && v < 15} bad={v => v > 30 || v < 0} />
                    <FundCell label="PD/DD (P/B)" val={fundamentals.pd_dd} good={v => v < 2} bad={v => v > 5} />
                    <FundCell label="Piyasa Değeri" val={fundamentals.piyasa_degeri} raw />
                    <FundCell label="Hisse Başı Kâr" val={fundamentals.eps} suffix=" ₺" />
                    <FundCell label="Temettü Verimi" val={fundamentals.temttu_verimi} suffix="%" good={v => v > 3} />
                    <FundCell label="Özkaynak Karl." val={fundamentals.roe} suffix="%" good={v => v > 15} bad={v => v < 0} />
                    <FundCell label="Aktif Karlılığı" val={fundamentals.roa} suffix="%" good={v => v > 5} bad={v => v < 0} />
                    <FundCell label="Borç/Özkaynak" val={fundamentals.borc_ozkaynak} good={v => v < 50} bad={v => v > 100} />
                    <FundCell label="Gelir Büyümesi" val={fundamentals.gelir_buyume} suffix="%" good={v => v > 10} bad={v => v < 0} />
                    <FundCell label="Brüt Kar Marjı" val={fundamentals.brut_kar_marji} suffix="%" good={v => v > 30} bad={v => v < 10} />
                    <FundCell label="Net Kar Marjı" val={fundamentals.net_kar_marji} suffix="%" good={v => v > 10} bad={v => v < 0} />
                    <FundCell label="Cari Oran" val={fundamentals.cari_oran} good={v => v > 1.5} bad={v => v < 1} />
                  </div>
                </div>
              )}

              {/* Balina & Akıllı Para Sinyalleri */}
              {whale && Object.keys(whale).length > 0 && (
                <div className="dp-whale-box">
                  <div className="dp-whale-hdr">
                    <span className="dp-whale-title">🐋 Balina & Akıllı Para Sinyalleri</span>
                    <span className="dp-whale-score" style={{
                      color: whale.whale_score >= 6.5 ? '#22c55e' : whale.whale_score <= 3.5 ? '#ef4444' : '#f59e0b'
                    }}>Skor: {whale.whale_score}/10</span>
                    <span className="dp-whale-sm" style={{
                      color: whale.smart_money?.includes('ALIYOR') ? '#22c55e' : whale.smart_money?.includes('SATIYOR') ? '#ef4444' : '#94a3b8'
                    }}>{whale.smart_money}</span>
                  </div>

                  <div className="dp-whale-grid">
                    {/* Akış Göstergeleri */}
                    <div className="dp-whale-col">
                      <div className="dp-whale-sec">Para Akışı Göstergeleri</div>
                      <WhaleRow label="OBV Trend"   val={whale.obv_trend === 'YUKSELIS' ? '↑ Yükseliş' : '↓ Düşüş'}
                        color={whale.obv_trend === 'YUKSELIS' ? '#22c55e' : '#ef4444'} />
                      {whale.obv_div && <WhaleRow label="OBV Div."  val={whale.obv_div}
                        color={whale.obv_div.includes('Boğa') ? '#22c55e' : '#f59e0b'} />}
                      <WhaleRow label="CMF (20)"    val={`${whale.cmf}  →  ${whale.cmf_state}`}
                        color={whale.cmf > 0.05 ? '#22c55e' : whale.cmf < -0.05 ? '#ef4444' : '#94a3b8'} />
                      <WhaleRow label="MFI (14)"    val={`${whale.mfi}  →  ${whale.mfi_state}`}
                        color={whale.mfi > 70 ? '#f59e0b' : whale.mfi < 30 ? '#22c55e' : '#60a5fa'} />
                      <WhaleRow label="A/D Çizgisi" val={whale.ad_trend === 'BIRIKIM' ? '↑ Birikim' : '↓ Dağıtım'}
                        color={whale.ad_trend === 'BIRIKIM' ? '#22c55e' : '#ef4444'} />
                    </div>

                    {/* Takas Proxy */}
                    <div className="dp-whale-col">
                      <div className="dp-whale-sec">Takas Proxy (Kurumsal/Perakende)</div>
                      <WhaleRow label="Net Akım"    val={whale.takas_signal}
                        color={whale.takas_signal?.includes('ALIM') ? '#22c55e' : whale.takas_signal?.includes('SATIM') ? '#ef4444' : '#94a3b8'} />
                      <WhaleRow label="Akım Skoru"  val={whale.takas_score > 0 ? `+${whale.takas_score}` : `${whale.takas_score}`}
                        color={whale.takas_score > 0.05 ? '#22c55e' : whale.takas_score < -0.05 ? '#ef4444' : '#94a3b8'} />

                      {whale.block_signals?.length > 0 && (
                        <>
                          <div className="dp-whale-sec" style={{marginTop:8}}>Blok İşlem Sinyalleri</div>
                          {whale.block_signals.map((b, i) => (
                            <WhaleRow key={i} label={b.date}
                              val={`${b.multiple}x hacim  ${b.price_chg >= 0 ? '+' : ''}${b.price_chg}%`}
                              color={b.direction === 'UP' ? '#22c55e' : '#ef4444'} />
                          ))}
                        </>
                      )}

                      {whale.gaps?.length > 0 && (
                        <>
                          <div className="dp-whale-sec" style={{marginTop:8}}>Gap Analizi</div>
                          {whale.gaps.map((g, i) => (
                            <WhaleRow key={i} label={g.date} val={`${g.type}  ${g.gap_pct > 0 ? '+' : ''}${g.gap_pct}%`}
                              color={g.gap_pct > 0 ? '#22c55e' : '#ef4444'} />
                          ))}
                        </>
                      )}
                    </div>

                    {/* Hacim Patlamaları */}
                    <div className="dp-whale-col">
                      <div className="dp-whale-sec">Hacim Patlamaları (son 30 gün)</div>
                      {whale.vol_spikes?.length > 0
                        ? whale.vol_spikes.map((s, i) => (
                            <WhaleRow key={i} label={s.date}
                              val={`${s.multiple}x   ${s.price_chg >= 0 ? '+' : ''}${s.price_chg}%`}
                              color={s.direction === 'UP' ? '#22c55e' : '#ef4444'} />
                          ))
                        : <span style={{fontSize:11,color:'#334155'}}>Son 30 günde anlamlı hacim patlaması yok.</span>
                      }
                    </div>
                  </div>
                  <div className="dp-whale-note">
                    ℹ Takas proxy, MKK resmi verisini değil yfinance OHLCV'den hesaplanan kurumsal birikim/dağıtım tahminini gösterir.
                  </div>
                </div>
              )}

              {/* Insider Tracker */}
              {insider && (insider.total_tx > 0 || insider.inst_holders?.length > 0) && (
                <div className="dp-insider-box">
                  <div className="dp-insider-hdr">
                    <span className="dp-insider-title">🕵️ Insider Tracker — {insider.data_type === 'form4' ? 'Yönetici İşlemleri (Form 4)' : 'Kurumsal Sahiplik Değişimi'}</span>
                    <span className="dp-insider-signal" style={{
                      color: insider.overall_color === 'bull' ? '#4ade80'
                           : insider.overall_color === 'warn' ? '#f59e0b'
                           : insider.overall_color === 'bear' ? '#f87171' : '#94a3b8'
                    }}>{insider.overall_signal}</span>
                    {insider.major?.insidersPercentHeld != null && (
                      <span className="dp-insider-meta">
                        İçeriden: %{insider.major.insidersPercentHeld} · Kurumsal: %{insider.major.institutionsPercentHeld}
                      </span>
                    )}
                  </div>

                  {/* Form 4 period tabs (US stocks) */}
                  {insider.data_type === 'form4' && insider.periods && (
                    <div className="dp-insider-periods">
                      {[['1g','Son 1 Gün'],['7g','Son 7 Gün'],['30g','Son 30 Gün'],['6ay','Son 6 Ay']].map(([k,lbl]) => {
                        const p = insider.periods[k]
                        if (!p) return null
                        return (
                          <div key={k} className="dp-insider-period">
                            <div className="dp-insider-period-hdr">
                              <span className="dp-ins-lbl">{lbl}</span>
                              <span className="dp-ins-signal" style={{
                                color: p.color === 'bull' ? '#4ade80'
                                     : p.color === 'warn' ? '#f59e0b'
                                     : p.color === 'bear' ? '#f87171' : '#94a3b8'
                              }}>{p.signal}</span>
                            </div>
                            <div className="dp-ins-stats">
                              <span className="dp-ins-buy">▲ {p.buy_count} alım</span>
                              <span className="dp-ins-sell">▼ {p.sell_count} satım</span>
                              {p.info_sell_cnt > 0 && (
                                <span className="dp-ins-warn">⚠ {p.info_sell_cnt} bilgisel satım</span>
                              )}
                            </div>
                            {p.transactions?.length > 0 && (
                              <div className="dp-ins-tx-list">
                                {p.transactions.map((tx, i) => (
                                  <div key={i} className={`dp-ins-tx ${tx.is_buy ? 'tx-buy' : tx.informative ? 'tx-info-sell' : 'tx-sell'}`}>
                                    <span className="dp-ins-tx-icon">{tx.is_buy ? '▲' : '▼'}</span>
                                    <div className="dp-ins-tx-body">
                                      <span className="dp-ins-tx-name">{tx.name}</span>
                                      <span className="dp-ins-tx-title">{tx.title}</span>
                                    </div>
                                    <div className="dp-ins-tx-right">
                                      <span className="dp-ins-tx-type">{tx.tx_type}</span>
                                      {tx.informative && <span className="dp-ins-tx-warn">BİLGİSEL</span>}
                                      <span className="dp-ins-tx-date">{tx.date}</span>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  )}

                  {/* Institutional holders (BIST proxy) */}
                  {insider.data_type === 'institutional' && insider.inst_holders?.length > 0 && (
                    <div className="dp-inst-table">
                      <div className="dp-ins-sec">Kurumsal Yatırımcı Pozisyon Değişimleri</div>
                      <div className="dp-inst-hdr-row">
                        <span>Kurum</span><span>Pay %</span><span>Değişim</span><span>Aksiyon</span>
                      </div>
                      {insider.inst_holders.map((h, i) => (
                        <div key={i} className="dp-inst-row">
                          <span className="dp-inst-name">{h.holder}</span>
                          <span className="dp-inst-pct">{h.pct_held}%</span>
                          <span className="dp-inst-chg" style={{
                            color: h.pct_chg > 0 ? '#4ade80' : h.pct_chg < 0 ? '#f87171' : '#94a3b8'
                          }}>{h.pct_chg > 0 ? '+' : ''}{h.pct_chg}%</span>
                          <span className="dp-inst-action" style={{
                            color: h.action === 'ALIM' ? '#4ade80' : h.action === 'SATIM' ? '#f87171' : '#94a3b8',
                            fontWeight: 700,
                          }}>{h.action}</span>
                        </div>
                      ))}
                    </div>
                  )}

                  <div className="dp-insider-note">
                    {insider.data_type === 'form4'
                      ? 'ℹ SEC Form 4 verisinden. "Bilgisel Satım": Üst yönetici, yüksek değerli, plan dışı satış.'
                      : 'ℹ BIST için KAP içeriden işlem verisi mevcut değil. Kurumsal sahiplik değişimi proxy olarak gösterilmektedir.'}
                  </div>
                </div>
              )}

              {/* Haber & Duygu Analizi */}
              {news?.sentiment_score && (
                <div className="dp-news-box">
                  <div className="dp-news-hdr">
                    <span className="dp-news-title">📰 Haber & Duygu Analizi{news.date_range ? ` (${news.date_range})` : ''}</span>
                    <span className="dp-news-emoji">{news.emoji}</span>
                    <div className="dp-news-score-wrap">
                      <div className="dp-news-score-bar">
                        <div className="dp-news-score-fill" style={{
                          width: `${(news.sentiment_score / 10) * 100}%`,
                          background: news.sentiment_score >= 6.5 ? '#22c55e' : news.sentiment_score >= 4.5 ? '#f59e0b' : '#ef4444',
                        }}/>
                      </div>
                      <span className="dp-news-score-num" style={{
                        color: news.sentiment_score >= 6.5 ? '#4ade80' : news.sentiment_score >= 4.5 ? '#fbbf24' : '#f87171'
                      }}>{news.sentiment_score}/10</span>
                    </div>
                    <span className="dp-news-label">{news.label}</span>
                    <span className="dp-news-meta">
                      {news.article_count} haber
                      {news.tr_count > 0 && ` · 🇹🇷 ${news.tr_count} TR`}
                      {news.en_count > 0 && ` · 🌐 ${news.en_count} EN`}
                      {' · '}+{news.pos_signals} olumlu / -{news.neg_signals} olumsuz
                    </span>
                  </div>

                  <div className="dp-news-cols">
                    {/* Top 3 drivers */}
                    {news.top_drivers?.length > 0 && (
                      <div className="dp-news-drivers">
                        <div className="dp-news-sec">🎯 En Etkili 3 Başlık</div>
                        {news.top_drivers.map((d, i) => (
                          <div key={i} className={`dp-news-driver ${d.direction === 'pos' ? 'drv-pos' : d.direction === 'neg' ? 'drv-neg' : 'drv-neu'}`}>
                            <span className="dp-news-drv-icon">{d.direction === 'pos' ? '▲' : d.direction === 'neg' ? '▼' : '●'}</span>
                            <span className="dp-news-drv-text">{d.title}</span>
                            <span className="dp-news-drv-pub">{d.publisher}</span>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Recent headlines */}
                    {news.headlines?.length > 0 && (
                      <div className="dp-news-feed">
                        <div className="dp-news-sec">📋 Son Haberler</div>
                        {news.headlines.map((h, i) => (
                          <div key={i} className="dp-news-item">
                            <span className="dp-news-date">{h.date}</span>
                            <span className="dp-news-text">{h.title}</span>
                            <span className="dp-news-pub">{h.publisher}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                  {news.sources_used?.length > 0 && (
                    <div className="dp-news-sources">
                      Kaynaklar: {news.sources_used.join(' · ')}
                    </div>
                  )}
                  <div className="dp-news-note">
                    ℹ Bloomberg HT, HaberTürk, Sabah, Sözcü, Para Analiz + Yahoo Finance. Keyword tabanlı duygu analizi — yatırım tavsiyesi değildir.
                  </div>
                </div>
              )}

            </div>{/* /dp-footer */}
          </div>
        ) : null}
      </div>
    </div>
  )
}

function Section({ title, children }) {
  return (
    <div className="dp-section">
      <div className="dp-sec-title">{title}</div>
      <div className="dp-sec-body">{children}</div>
    </div>
  )
}

function Row({ label, val, color }) {
  return (
    <div className="dp-row">
      <span className="dp-row-lbl">{label}</span>
      <span className="dp-row-val" style={{color: color||'#94a3b8'}}>{val}</span>
    </div>
  )
}

function WhaleRow({ label, val, color }) {
  return (
    <div className="dp-whale-row">
      <span className="dp-whale-lbl">{label}</span>
      <span className="dp-whale-val" style={{color: color||'#94a3b8'}}>{val}</span>
    </div>
  )
}

function FundCell({ label, val, suffix='', raw=false, good, bad }) {
  if (val === null || val === undefined) {
    return (
      <div className="dp-fund-cell">
        <span className="dp-fund-lbl">{label}</span>
        <span className="dp-fund-val" style={{color:'#334155'}}>—</span>
      </div>
    )
  }
  const display = raw ? val : `${val}${suffix}`
  let color = '#94a3b8'
  if (!raw) {
    const n = parseFloat(val)
    if (!isNaN(n)) {
      if (good && good(n)) color = '#4ade80'
      else if (bad && bad(n)) color = '#f87171'
    }
  }
  return (
    <div className="dp-fund-cell">
      <span className="dp-fund-lbl">{label}</span>
      <span className="dp-fund-val" style={{color}}>{display}</span>
    </div>
  )
}
