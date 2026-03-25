import { useEffect, useRef, useState } from 'react'
import { createChart, CrosshairMode, LineStyle, CandlestickSeries, LineSeries, createSeriesMarkers } from 'lightweight-charts'
import './PatternChart.css'

const DIR_COLOR = {
  bullish: '#22c55e',
  bearish: '#ef4444',
  neutral: '#60a5fa',
}

// ── Order Block detection ─────────────────────────────────────────────
function detectOrderBlocks(candles) {
  const zones = []
  const n = candles.length
  const slice = candles.slice(Math.max(0, n - 120))

  for (let i = 0; i < slice.length - 4; i++) {
    const c = slice[i]
    const bodySize = Math.abs(c.open - c.close)
    if (bodySize < (c.high - c.low) * 0.1) continue // ignore doji

    // Bullish OB: bearish candle + strong impulse up
    if (c.close < c.open) {
      const impulseHigh = Math.max(slice[i+1].high, slice[i+2]?.high ?? 0, slice[i+3]?.high ?? 0)
      if (impulseHigh > c.high * 1.004) {
        const top = c.open, bottom = c.close
        const breached = slice.slice(i + 3).some(x => x.close < bottom * 0.999)
        if (!breached) zones.push({ type: 'bull_ob', top, bottom, startTime: c.time, color: '#22c55e' })
      }
    }

    // Bearish OB: bullish candle + strong impulse down
    if (c.close > c.open) {
      const impulseLow = Math.min(slice[i+1].low, slice[i+2]?.low ?? Infinity, slice[i+3]?.low ?? Infinity)
      if (impulseLow < c.low * 0.996) {
        const top = c.close, bottom = c.open
        const breached = slice.slice(i + 3).some(x => x.close > top * 1.001)
        if (!breached) zones.push({ type: 'bear_ob', top, bottom, startTime: c.time, color: '#ef4444' })
      }
    }
  }

  const bull = zones.filter(z => z.type === 'bull_ob').slice(-3)
  const bear = zones.filter(z => z.type === 'bear_ob').slice(-3)
  return [...bull, ...bear]
}

// ── Supply / Demand zone detection ───────────────────────────────────
function detectSupplyDemand(candles) {
  const zones = []
  const n = candles.length
  const slice = candles.slice(Math.max(0, n - 120))

  for (let i = 2; i < slice.length - 3; i++) {
    const prev = slice[i-1], c = slice[i], next = slice[i+1], next2 = slice[i+2]

    // Demand: swing low + strong up move after
    if (c.low < prev.low && c.low < next.low) {
      const upMove = Math.max(next.high, next2.high) - c.high
      const range = c.high - c.low
      if (upMove > range * 0.4 && range > 0) {
        const top = Math.max(c.open, c.close)
        const bottom = c.low
        const breached = slice.slice(i + 2).some(x => x.close < bottom * 0.998)
        if (!breached) zones.push({ type: 'demand', top, bottom, startTime: c.time, color: '#0ea5e9' })
      }
    }

    // Supply: swing high + strong down move after
    if (c.high > prev.high && c.high > next.high) {
      const downMove = c.low - Math.min(next.low, next2.low)
      const range = c.high - c.low
      if (downMove > range * 0.4 && range > 0) {
        const top = c.high
        const bottom = Math.min(c.open, c.close)
        const breached = slice.slice(i + 2).some(x => x.close > top * 1.002)
        if (!breached) zones.push({ type: 'supply', top, bottom, startTime: c.time, color: '#f97316' })
      }
    }
  }

  const demand = zones.filter(z => z.type === 'demand').slice(-3)
  const supply = zones.filter(z => z.type === 'supply').slice(-3)
  return [...demand, ...supply]
}

// ── Canvas primitive: draws filled zone rectangles ────────────────────
class ZonesPrimitive {
  constructor(zones) {
    this._zones = zones
    this._chart = null
    this._series = null
    // Use `self` so draw() always sees current refs
    const self = this
    this._view = {
      zOrder() { return 'bottom' },
      renderer() {
        return {
          draw(target) {
            if (!self._chart || !self._series) return
            try {
              target.useBitmapCoordinateSpace(({ context: ctx, bitmapSize, horizontalPixelRatio, verticalPixelRatio }) => {
                const ts = self._chart.timeScale()
                self._zones.forEach(({ top, bottom, startTime, color, type }) => {
                  const x1 = ts.timeToCoordinate(startTime)
                  if (x1 === null) return
                  const y1 = self._series.priceToCoordinate(top)
                  const y2 = self._series.priceToCoordinate(bottom)
                  if (y1 === null || y2 === null) return

                  const rx1 = Math.max(0, x1 * horizontalPixelRatio)
                  const rx2 = bitmapSize.width
                  const ry1 = Math.min(y1, y2) * verticalPixelRatio
                  const ry2 = Math.max(y1, y2) * verticalPixelRatio
                  const rh  = Math.max(ry2 - ry1, 2)
                  const rw  = rx2 - rx1

                  ctx.fillStyle = color + '22'
                  ctx.fillRect(rx1, ry1, rw, rh)

                  ctx.strokeStyle = color + 'aa'
                  ctx.lineWidth = 1
                  ctx.beginPath()
                  ctx.moveTo(rx1, ry1); ctx.lineTo(rx2, ry1)
                  ctx.moveTo(rx1, ry2); ctx.lineTo(rx2, ry2)
                  ctx.stroke()

                  const label = type === 'bull_ob' ? 'OB▲' : type === 'bear_ob' ? 'OB▼' : type === 'demand' ? 'D' : 'S'
                  const fs = Math.round(9 * Math.min(horizontalPixelRatio, verticalPixelRatio))
                  ctx.font = `bold ${fs}px monospace`
                  ctx.fillStyle = color + 'dd'
                  ctx.fillText(label, rx1 + 3, ry1 + fs + 1)
                })
              })
            } catch (_) {}
          }
        }
      }
    }
  }

  attached({ chart, series }) { this._chart = chart; this._series = series }
  detached() { this._chart = null; this._series = null }
  updateAllViews() {}
  paneViews() { return [this._view] }
}

// ── TD Sequential calculation ─────────────────────────────────────────
function calcTDSequential(candles) {
  const result = []
  let buyCount = 0, sellCount = 0

  for (let i = 4; i < candles.length; i++) {
    const c = candles[i], ref = candles[i - 4]
    const isBuy  = c.close < ref.close
    const isSell = c.close > ref.close

    if (isBuy) {
      buyCount++; sellCount = 0
      if (buyCount <= 9) result.push({ time: c.time, count: buyCount, type: 'buy', low: c.low })
    } else if (isSell) {
      sellCount++; buyCount = 0
      if (sellCount <= 9) result.push({ time: c.time, count: sellCount, type: 'sell', high: c.high })
    } else {
      buyCount = 0; sellCount = 0
    }
  }
  // Only show last 60 candles worth
  const cutoff = candles.length > 60 ? candles[candles.length - 61].time : 0
  return result.filter(r => r.time > cutoff)
}

// ── TD Sequential canvas primitive ───────────────────────────────────
class TDPrimitive {
  constructor(tdData) {
    this._td = tdData
    this._chart = null
    this._series = null
    const self = this
    this._view = {
      renderer() {
        return {
          draw(target) {
            if (!self._chart || !self._series) return
            try {
              target.useBitmapCoordinateSpace(({ context: ctx, horizontalPixelRatio, verticalPixelRatio }) => {
                const ts = self._chart.timeScale()
                self._td.forEach(({ time, count, type, low, high }) => {
                  const x = ts.timeToCoordinate(time)
                  if (x === null) return
                  const py = type === 'buy'
                    ? self._series.priceToCoordinate(low)
                    : self._series.priceToCoordinate(high)
                  if (py === null) return

                  const isKey = count === 9
                  const color = type === 'buy' ? '#4ade80' : '#f87171'
                  const fs = Math.round((isKey ? 11 : 8) * Math.min(horizontalPixelRatio, verticalPixelRatio))
                  const px = x * horizontalPixelRatio
                  const gap = 10 * verticalPixelRatio

                  ctx.font = `${isKey ? 'bold' : 'normal'} ${fs}px monospace`
                  ctx.fillStyle = isKey ? color : color + '99'
                  ctx.textAlign = 'center'

                  if (type === 'buy') {
                    ctx.fillText(String(count), px, py * verticalPixelRatio + gap + fs)
                  } else {
                    ctx.fillText(String(count), px, py * verticalPixelRatio - gap)
                  }
                })
              })
            } catch (_) {}
          }
        }
      }
    }
  }

  attached({ chart, series }) { this._chart = chart; this._series = series }
  detached() { this._chart = null; this._series = null }
  updateAllViews() {}
  paneViews() { return [this._view] }
}

// Pattern key levels to draw as horizontal lines
function getPatternLevels(pattern) {
  const levels = []
  if (pattern.neckline   != null) levels.push({ price: pattern.neckline,   color: '#f59e0b', label: 'Boyun', dash: true })
  if (pattern.target     != null) levels.push({ price: pattern.target,     color: DIR_COLOR[pattern.direction] || '#60a5fa', label: 'Hedef', dash: false })
  if (pattern.support    != null) levels.push({ price: pattern.support,    color: '#22c55e', label: 'Destek', dash: true })
  if (pattern.resistance != null) levels.push({ price: pattern.resistance, color: '#ef4444', label: 'Direnç', dash: true })
  return levels
}

// levels = [{ price, color, label, dash }]
export default function PatternChart({ ticker, patterns, price, levels: extraLevels, interval = '1d', days = 180 }) {
  const containerRef = useRef(null)
  const chartRef     = useRef(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)
  const [showOB, setShowOB]   = useState(true)
  const [showSD, setShowSD]   = useState(true)
  const [showTD, setShowTD]   = useState(true)

  useEffect(() => {
    if (!ticker || !containerRef.current) return

    // Cleanup previous chart
    if (chartRef.current) {
      chartRef.current.remove()
      chartRef.current = null
    }

    setLoading(true)
    setError(null)

    const chart = createChart(containerRef.current, {
      autoSize: true,
      height: 340,
      layout: {
        background: { color: '#080e1a' },
        textColor:  '#64748b',
      },
      grid: {
        vertLines:  { color: '#0f1e30', style: LineStyle.Dotted },
        horzLines:  { color: '#0f1e30', style: LineStyle.Dotted },
      },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: {
        borderColor: '#1e293b',
        textColor:   '#475569',
      },
      timeScale: {
        borderColor:       '#1e293b',
        timeVisible:       true,
        secondsVisible:    false,
        tickMarkFormatter: (ts) => {
          const d = new Date(ts * 1000)
          return `${d.getDate().toString().padStart(2,'0')}/${(d.getMonth()+1).toString().padStart(2,'0')}`
        },
      },
    })
    chartRef.current = chart

    // Candlestick series (v5 API)
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor:          '#22c55e',
      downColor:        '#ef4444',
      borderUpColor:    '#22c55e',
      borderDownColor:  '#ef4444',
      wickUpColor:      '#22c55e',
      wickDownColor:    '#ef4444',
    })

    // Fetch OHLCV
    fetch(`/api/stock/${ticker}/ohlcv?days=${days}&interval=${interval}`)
      .then(r => r.json())
      .then(json => {
        if (json.error || !json.data?.length) {
          setError('Veri alınamadı')
          setLoading(false)
          return
        }

        const candles = json.data.sort((a, b) => a.time - b.time)
        candleSeries.setData(candles)

        // ── Draw level lines (pattern levels + extra from caller) ──
        const allLevels = []
        const topPat = patterns?.[0]
        if (topPat) allLevels.push(...getPatternLevels(topPat))
        if (extraLevels?.length) allLevels.push(...extraLevels)

        // Merge labels that are within 1.5% of each other to prevent overlap
        const sorted = [...allLevels].filter(l => l.price).sort((a, b) => b.price - a.price)
        const merged = []
        for (const lvl of sorted) {
          const prev = merged[merged.length - 1]
          if (prev && Math.abs(lvl.price - prev.price) / prev.price < 0.015) {
            prev.label = prev.label + '/' + lvl.label
          } else {
            merged.push({ ...lvl })
          }
        }

        const first = candles[0].time
        const last  = candles[candles.length - 1].time
        merged.forEach(({ price: lp, color, label, dash }) => {
          if (!lp) return
          const line = chart.addSeries(LineSeries, {
            color,
            lineWidth:    1,
            lineStyle:    dash ? LineStyle.Dashed : LineStyle.Solid,
            priceLineVisible: false,
            lastValueVisible: true,
            title: label,
          })
          line.setData([{ time: first, value: lp }, { time: last, value: lp }])
        })

        // ── Price markers for each pattern ────────────────────────
        if (patterns?.length) {
          const markers = []

          patterns.forEach(pat => {
            const color = DIR_COLOR[pat.direction] || '#60a5fa'
            const shape = pat.direction === 'bullish' ? 'arrowUp' : pat.direction === 'bearish' ? 'arrowDown' : 'circle'
            const pos   = pat.direction === 'bullish' ? 'belowBar' : pat.direction === 'bearish' ? 'aboveBar' : 'inBar'

            // Place marker at recent candle (80% through the data)
            const idx = Math.floor(candles.length * 0.8)
            const refCandle = candles[Math.min(idx, candles.length - 1)]
            if (!refCandle) return

            // Avoid duplicate timestamps
            const existing = markers.find(m => m.time === refCandle.time)
            markers.push({
              time:  existing ? refCandle.time + markers.length : refCandle.time,
              position: pos,
              color,
              shape,
              text:  pat.name,
              size:  1,
            })
          })

          // Sort markers by time (required)
          markers.sort((a, b) => a.time - b.time)
          // v5: createSeriesMarkers plugin
          createSeriesMarkers(candleSeries, markers)
        }

        // ── Order Blocks ──────────────────────────────────────────
        if (showOB) {
          const obs = detectOrderBlocks(candles)
          if (obs.length) candleSeries.attachPrimitive(new ZonesPrimitive(obs))
        }

        // ── Supply / Demand zones ─────────────────────────────────
        if (showSD) {
          const sdZones = detectSupplyDemand(candles)
          if (sdZones.length) candleSeries.attachPrimitive(new ZonesPrimitive(sdZones))
        }

        // ── TD Sequential ─────────────────────────────────────────
        if (showTD) {
          const tdData = calcTDSequential(candles)
          if (tdData.length) candleSeries.attachPrimitive(new TDPrimitive(tdData))
        }

        // ── Current price line ────────────────────────────────────
        candleSeries.createPriceLine({
          price:     price,
          color:     '#38bdf8',
          lineWidth: 1,
          lineStyle: LineStyle.Solid,
          axisLabelVisible: true,
          title: 'Şu an',
        })

        chart.timeScale().fitContent()
        setLoading(false)
      })
      .catch(e => {
        setError(e.message)
        setLoading(false)
      })

    return () => {
      if (chartRef.current) {
        chartRef.current.remove()
        chartRef.current = null
      }
    }
  }, [ticker, interval, days, showOB, showSD, showTD])

  return (
    <div className="pc-wrap">
      <div className="pc-header">
        <span className="pc-title">📈 {ticker} — Formasyon Grafiği</span>
        <div className="pc-legend">
          {patterns?.map((p, i) => (
            <span key={i} className="pc-legend-item" style={{ color: DIR_COLOR[p.direction] || '#60a5fa' }}>
              {p.direction === 'bullish' ? '↑' : p.direction === 'bearish' ? '↓' : '↔'} {p.name}
            </span>
          ))}
        </div>
        <div className="pc-toggles">
          <button className={`pc-tog ${showOB ? 'pc-tog-on' : ''}`} onClick={() => setShowOB(v => !v)} title="Order Blocks">OB</button>
          <button className={`pc-tog ${showSD ? 'pc-tog-on' : ''}`} onClick={() => setShowSD(v => !v)} title="Supply & Demand">S/D</button>
          <button className={`pc-tog ${showTD ? 'pc-tog-on' : ''}`} onClick={() => setShowTD(v => !v)} title="TD Sequential">TD</button>
        </div>
      </div>

      {loading && (
        <div className="pc-loading">
          <div className="pc-spinner"/>
          <span>Grafik yükleniyor…</span>
        </div>
      )}
      {error && <div className="pc-error">{error}</div>}

      <div ref={containerRef} className="pc-chart" style={{ display: loading || error ? 'none' : 'block' }}/>

      {/* Level legend */}
      {!loading && !error && (() => {
        const allL = [
          ...(patterns?.[0] ? getPatternLevels(patterns[0]) : []),
          ...(extraLevels || []),
        ]
        if (!allL.length) return null
        return (
          <div className="pc-levels">
            {allL.map((l, i) => (
              <span key={i} className="pc-lvl" style={{ color: l.color }}>
                {l.dash ? '- - ' : '—— '}{l.label}: ₺{l.price?.toFixed(2)}
              </span>
            ))}
          </div>
        )
      })()}
    </div>
  )
}
