import { useState } from 'react'
import './StockCard.css'
const TV = 'https://www.tradingview.com/chart/?symbol=BIST:'

function actCls(action) {
  return action === 'GÜÇLÜ AL' ? 'act-strong'
       : action === 'AL'       ? 'act-buy'
       : action === 'İZLE'     ? 'act-watch'
       : action === 'ZAYIF'    ? 'act-weak'
       :                         'act-sell'
}
function scoreColor(score) {
  return score >= 7.5 ? '#f59e0b' : score >= 6 ? '#22c55e'
       : score >= 4.5 ? '#60a5fa' : '#ef4444'
}

export default function StockCard({ stock, onDetail, isFav, onToggleFav }) {
  const [tfTab, setTfTab] = useState('genel')

  const { ticker, price, change_pct, price_label, last_bar_date,
    weekly_bias, long_pct, short_pct, market_strength, ai_confidence,
    rsi, rel_vol, trend, macd_signal, bull_ob, sl, tp1, tp2,
    risk_pct, rr, bull_fvg, liq_sweep, setup_type, stats, ai_score, ai_action,
    bullets, news, insider,
    tf_4h, tf_1d, tf_1w, tf_1mo, action_4h, action_1d, action_1w, action_1mo
  } = stock

  const pos = change_pct >= 0
  const bullish = long_pct > 50
  const wIcon = weekly_bias === 'Yükseliş' ? '✓' : weekly_bias === 'Düşüş' ? '⚠' : '○'
  const wCls  = weekly_bias === 'Yükseliş' ? 'w-bull' : weekly_bias === 'Düşüş' ? 'w-bear' : 'w-neut'

  // Aktif sekme verisi
  const tfData = tfTab === 'genel' ? { tf: null,   action: ai_action,  label: 'Genel'    }
               : tfTab === '4h'   ? { tf: tf_4h,  action: action_4h,  label: '4 Saat'   }
               : tfTab === '1d'   ? { tf: tf_1d,  action: action_1d,  label: 'Günlük'   }
               : tfTab === '1w'   ? { tf: tf_1w,  action: action_1w,  label: 'Haftalık'  }
               :                   { tf: tf_1mo, action: action_1mo, label: 'Aylık'    }
  const curAction  = tfData.action || ai_action
  const curScore   = tfTab === 'genel' ? ai_score : (tfData.tf?.score ?? ai_score)
  const curBullets = tfTab === 'genel' ? (bullets ?? []) : (tfData.tf?.reasons ?? bullets ?? [])

  return (
    <div className="card" onClick={onDetail} title="Detaylı analiz için tıkla">

      {/* Üst — ticker + fiyat */}
      <div className="card-top">
        <div className="top-row">
          <button
            className={`fav-btn ${isFav ? 'fav-on' : ''}`}
            onClick={e => { e.stopPropagation(); onToggleFav && onToggleFav() }}
            title={isFav ? 'Favorilerden çıkar' : 'Favorilere ekle'}
          >{isFav ? '★' : '☆'}</button>
          <span className="ticker">{ticker}</span>
          <span className={`zone-tag ${price_label === 'PAHALI' ? 'zt-pahali' : 'zt-ucuz'}`}>{price_label}</span>
          <span className={`bias-tag ${bullish ? 'bt-bull' : 'bt-bear'}`}>
            {bullish ? '⬆ YUKSELIŞ' : '⬇ DÜŞÜŞ'} BİAS
          </span>
          <span className="price">₺{price?.toLocaleString('tr-TR',{minimumFractionDigits:1,maximumFractionDigits:2})}</span>
          <span className={`chg ${pos?'pos':'neg'}`}>{pos?'+':''}{change_pct?.toFixed(2)}%</span>
        </div>
        <div className="sub-row">
          <span className="last-bar">Son kapanış: {last_bar_date}</span>
          <span className={`weekly-tag ${wCls}`}>{wIcon} Haftalık {weekly_bias}</span>
          <span className="detail-hint">👁 Detay</span>
        </div>
      </div>

      {/* Long/Short bar */}
      <div className="ls-wrap">
        <span className="ls-lbl ls-green">LONG %{long_pct}</span>
        <span className="ls-lbl ls-red">SHORT %{short_pct}</span>
        <div className="ls-bar">
          <div className="ls-long" style={{width:`${long_pct}%`}}/>
          <div className="ls-short" style={{width:`${short_pct}%`}}/>
        </div>
      </div>

      {/* 4 kutu */}
      <div className="stat-grid">
        <Stat label="Market Gücü"  val={`%${market_strength}`}/>
        <Stat label="AI Güveni"    val={`%${ai_confidence}`}/>
        <Stat label="RSI" val={rsi?.toFixed(1)}
          color={rsi>70?'#ef4444':rsi<30?'#22c55e':'#38bdf8'}/>
        <Stat label="Rel. Hacim"   val={`${rel_vol}x`}
          color={rel_vol>1.5?'#22c55e':rel_vol<0.7?'#ef4444':'#94a3b8'}/>
      </div>

      {/* Trend rozeti */}
      <div className="trend-row">
        <span className={`trend-badge ${trend==='BOĞA'?'tb-bull':'tb-bear'}`}>
          {trend==='BOĞA'?'🐂 BOĞA TRENDİ':'🐻 AYI TRENDİ'}
        </span>
        {setup_type === 'KIRILIM' && (
          <span className="setup-badge sb-kirilim">💥 KIRILIM</span>
        )}
        {setup_type === 'DÖNÜŞ' && (
          <span className="setup-badge sb-donus">↩ DÖNÜŞ</span>
        )}
        {liq_sweep && (
          <span className={`sweep-badge ${liq_sweep.bull?'sb-bull':'sb-bear'}`}>
            🧹 {liq_sweep.type}
          </span>
        )}
      </div>

      {/* MACD */}
      {macd_signal && (
        <div className={`sig-row ${macd_signal.bullish?'sr-bull':'sr-bear'}`}>
          <span className="sig-name">MACD {macd_signal.type}</span>
          <span className="sig-val">{macd_signal.value}</span>
          <span className="sig-date">{macd_signal.date}</span>
        </div>
      )}

      {/* Bullish OB */}
      {bull_ob && (
        <div className="ob-box">
          <div className="ob-head">
            <span className="ob-label">🟩 Bullish OB</span>
            <span className="ob-price">{bull_ob.price}</span>
            <span className="ob-date">{bull_ob.date}</span>
          </div>
          <div className="sltp-row">
            <div className="sl-box">ZK: ₺{sl}</div>
            <div className="tp1-box">H1: ₺{tp1}</div>
            <div className="tp2-box">H2: ₺{tp2}</div>
          </div>
          <div className="rr-row">
            <span>Risk: %{risk_pct}</span>
            <span>R:R = 1:{rr}</span>
          </div>
        </div>
      )}

      {/* FVG */}
      {bull_fvg && (
        <div className="sig-row sr-fvg">
          <span className="sig-name">📐 Bullish FVG</span>
          <span className="sig-val">{bull_fvg.price}</span>
          <span className="sig-date">{bull_fvg.date}</span>
        </div>
      )}

      {/* İstatistik */}
      {stats && (
        <div className="istat-box">
          <span className="istat-title">📊 Geçmiş Veri</span>
          <span className="istat-row">Hareketli günler: {stats.best_days?.join(', ')}</span>
          <span className="istat-row">Aktif saatler: {stats.best_hours?.join(', ')}</span>
          <span className="istat-row">Ort. günlük aralık: %{stats.avg_daily_range_pct}</span>
        </div>
      )}

      {/* Insider Badge */}
      {insider?.overall_signal && (
        <div className="insider-bar">
          <span className="insider-icon">🕵️</span>
          <span className="insider-label">Insider</span>
          <span className="insider-signal" style={{
            color: insider.overall_color === 'bull' ? '#4ade80'
                 : insider.overall_color === 'warn' ? '#f59e0b'
                 : insider.overall_color === 'bear' ? '#f87171' : '#94a3b8'
          }}>{insider.overall_signal}</span>
          <span className="insider-cnt">{insider.total_tx} işlem</span>
        </div>
      )}

      {/* Haber Duygu */}
      {news?.sentiment_score && (
        <div className="news-bar">
          <span className="news-emoji">{news.emoji}</span>
          <span className="news-label">Haber Duygusu</span>
          <div className="news-track">
            <div className="news-fill" style={{
              width: `${(news.sentiment_score / 10) * 100}%`,
              background: news.sentiment_score >= 6 ? '#22c55e' : news.sentiment_score >= 4 ? '#f59e0b' : '#ef4444',
            }}/>
          </div>
          <span className="news-score" style={{
            color: news.sentiment_score >= 6 ? '#4ade80' : news.sentiment_score >= 4 ? '#fbbf24' : '#f87171'
          }}>{news.sentiment_score}/10</span>
          <span className="news-tag">{news.label}</span>
          <span className="news-cnt">{news.article_count} haber</span>
        </div>
      )}

      {/* AI Analiz — çok zaman dilimi */}
      <div className="ai-box">
        <div className="ai-hdr">
          <span className="ai-title">◈ THS AI Analizi</span>
          <span className="ai-score" style={{color:scoreColor(ai_score),borderColor:scoreColor(ai_score)}}>
            Genel: {ai_score}
          </span>
        </div>

        {/* Sekme seçici */}
        <div className="tf-tabs" onClick={e => e.stopPropagation()}>
          {[
            { key: 'genel', label: 'Genel',   score: ai_score,      action: ai_action  },
            { key: '4h',    label: '4s',       score: tf_4h?.score,  action: action_4h  },
            { key: '1d',    label: 'Günlük',   score: tf_1d?.score,  action: action_1d  },
            { key: '1w',    label: 'Haftalık', score: tf_1w?.score,  action: action_1w  },
            { key: '1mo',   label: 'Aylık',    score: tf_1mo?.score, action: action_1mo },
          ].map(({ key, label, score, action }) => (
            <button
              key={key}
              className={`tf-tab ${tfTab === key ? 'tf-tab-active' : ''}`}
              onClick={() => setTfTab(key)}
            >
              <span className="tf-tab-label">{label}</span>
              {score != null && (
                <span className="tf-tab-score" style={{color: scoreColor(score)}}>{score}</span>
              )}
              {action && (
                <span className={`tf-tab-action tfa-${actCls(action)}`}>{action}</span>
              )}
            </button>
          ))}
        </div>

        {/* Aktif sekme içeriği */}
        <>
          <button className={`act-btn ${actCls(curAction)}`} onClick={e=>{e.stopPropagation();onDetail()}}>
            {curAction}
          </button>
          {tfData.tf && (
            <div className="tf-meta-row">
              <span className="tf-meta-item">RSI <b style={{color: tfData.tf.rsi > 70 ? '#ef4444' : tfData.tf.rsi < 30 ? '#22c55e' : '#38bdf8'}}>{tfData.tf.rsi?.toFixed(1)}</b></span>
              <span className="tf-meta-item">Trend <b style={{color: tfData.tf.trend === 'BOĞA' ? '#22c55e' : '#ef4444'}}>{tfData.tf.trend}</b></span>
              <span className="tf-meta-item">Yapı <b style={{color: tfData.tf.market_structure === 'YUKSELIS' ? '#22c55e' : tfData.tf.market_structure === 'DUSUS' ? '#ef4444' : '#94a3b8'}}>{tfData.tf.market_structure === 'YUKSELIS' ? 'YÜKSELİŞ' : tfData.tf.market_structure === 'DUSUS' ? 'DÜŞÜŞ' : 'YATAY'}</b></span>
            </div>
          )}
          {curBullets.length > 0 && (
            <ul className="bullets">
              {curBullets.slice(0,5).map((b,i)=><li key={i}>{b}</li>)}
            </ul>
          )}
        </>
      </div>

      {/* TradingView */}
      <a href={`${TV}${ticker}`} target="_blank" rel="noopener noreferrer"
        className="tv-link" onClick={e=>e.stopPropagation()}>
        ⬡ Grafiği TradingView'da Aç
      </a>
    </div>
  )
}

function Stat({label, val, color}) {
  return (
    <div className="stat-box">
      <span className="stat-lbl">{label}</span>
      <span className="stat-val" style={{color: color||'#38bdf8'}}>{val}</span>
    </div>
  )
}
