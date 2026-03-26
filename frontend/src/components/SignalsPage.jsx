import { useState, useEffect } from 'react'
import './SignalsPage.css'

const ACTION_CLS = {
  'GÜÇLÜ AL': 'sig-strong',
  'AL':        'sig-buy',
  'İZLE':      'sig-watch',
  'ZAYIF':     'sig-weak',
  'SAT':       'sig-sell',
}

const TF_TABS = [
  { key: 'genel', label: 'Genel',    actionKey: 'action',    scoreKey: 'score'    },
  { key: '4h',    label: '4 Saat',   actionKey: 'action_4h', scoreKey: 'score_4h' },
  { key: '1d',    label: 'Günlük',   actionKey: 'action_1d', scoreKey: 'score_1d' },
  { key: '1w',    label: 'Haftalık', actionKey: 'action_1w', scoreKey: 'score_1w' },
  { key: '1mo',   label: 'Aylık',    actionKey: 'action_1mo',scoreKey: 'score_1mo'},
]

const ALL_TF_COLS = [
  { key: 'score',     label: 'Genel',  actionKey: 'action',     scoreKey: 'score'     },
  { key: 'score_4h',  label: '4S',     actionKey: 'action_4h',  scoreKey: 'score_4h'  },
  { key: 'score_1d',  label: 'Gün',    actionKey: 'action_1d',  scoreKey: 'score_1d'  },
  { key: 'score_1w',  label: 'Hft',    actionKey: 'action_1w',  scoreKey: 'score_1w'  },
  { key: 'score_1mo', label: 'Aylık',  actionKey: 'action_1mo', scoreKey: 'score_1mo' },
]

export default function SignalsPage({ onBack, onTickerClick }) {
  const [signals, setSignals]   = useState([])
  const [loading, setLoading]   = useState(true)
  const [limit, setLimit]       = useState(100)
  const [tfTab, setTfTab]       = useState('genel')
  const [actionF, setActionF]   = useState('TÜMÜ')
  const [sortCol, setSortCol]   = useState('created_at')
  const [sortDir, setSortDir]   = useState('desc')

  useEffect(() => {
    setLoading(true)
    fetch(`/api/signals/recent?limit=${limit}`)
      .then(r => r.json())
      .then(d => { setSignals(d.signals || []); setLoading(false) })
      .catch(() => setLoading(false))
  }, [limit])

  const curTab = TF_TABS.find(t => t.key === tfTab)

  // Her satır için aktif sekmenin aksiyonunu ve skorunu al
  const withTf = signals.map(s => ({
    ...s,
    curAction: s[curTab.actionKey] || s.action,
    curScore:  s[curTab.scoreKey]  ?? s.score,
  }))

  const filtered = actionF === 'TÜMÜ'
    ? withTf
    : withTf.filter(s => s.curAction === actionF)

  const ACTION_ORDER = ['GÜÇLÜ AL','AL','İZLE','ZAYIF','SAT']

  const handleSort = (col) => {
    if (sortCol === col) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortCol(col); setSortDir('asc') }
  }

  const sorted = [...filtered].sort((a, b) => {
    let av = a[sortCol], bv = b[sortCol]
    if (sortCol === 'curAction' || sortCol === 'action') {
      av = ACTION_ORDER.indexOf(av ?? '')
      bv = ACTION_ORDER.indexOf(bv ?? '')
    } else if (sortCol === 'created_at') {
      av = new Date(av); bv = new Date(bv)
    } else if (sortCol === 'ticker') {
      av = av ?? ''; bv = bv ?? ''
      return sortDir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av)
    } else {
      av = av ?? -Infinity; bv = bv ?? -Infinity
    }
    if (av < bv) return sortDir === 'asc' ? -1 : 1
    if (av > bv) return sortDir === 'asc' ? 1 : -1
    return 0
  })

  const sortIcon = (col) => sortCol === col ? (sortDir === 'asc' ? ' ▲' : ' ▼') : ' ⇅'

  const actionCounts = withTf.reduce((acc, s) => {
    const a = s.curAction
    if (a) acc[a] = (acc[a] || 0) + 1
    return acc
  }, {})

  return (
    <div className="sig-page">
      <div className="sig-header">
        <button className="back-btn" onClick={onBack}>← Geri</button>
        <h1 className="sig-title">🔔 Sinyal Geçmişi</h1>
        <span className="sig-sub">Veritabanına kaydedilen son sinyaller</span>
      </div>

      {/* Zaman dilimi sekmeleri */}
      <div className="sig-tf-tabs">
        {TF_TABS.map(t => (
          <button
            key={t.key}
            className={`sig-tf-tab ${tfTab === t.key ? 'sig-tf-active' : ''}`}
            onClick={() => { setTfTab(t.key); setActionF('TÜMÜ') }}
          >{t.label}</button>
        ))}
      </div>

      {/* Özet */}
      <div className="sig-summary">
        {['GÜÇLÜ AL','AL','İZLE','ZAYIF','SAT']
          .filter(a => actionCounts[a])
          .map(action => (
            <div key={action} className={`sig-summary-badge ${ACTION_CLS[action] || ''}`}>
              <span className="ssb-action">{action}</span>
              <span className="ssb-cnt">{actionCounts[action]}</span>
            </div>
          ))}
      </div>

      {/* Filtreler */}
      <div className="sig-controls">
        <div className="sig-ctrl-group">
          <span className="sig-ctrl-label">Sinyal</span>
          {['TÜMÜ','GÜÇLÜ AL','AL','İZLE','ZAYIF','SAT'].map(a => (
            <button key={a}
              className={`sig-pill ${actionF === a ? 'sig-pill-active' : ''}`}
              onClick={() => setActionF(a)}
            >{a}</button>
          ))}
        </div>
        <div className="sig-ctrl-group">
          <span className="sig-ctrl-label">Limit</span>
          {[50, 100, 250, 500].map(l => (
            <button key={l}
              className={`sig-pill ${limit === l ? 'sig-pill-active' : ''}`}
              onClick={() => setLimit(l)}
            >{l}</button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="sig-loading"><div className="spinner"/> Yükleniyor…</div>
      ) : filtered.length === 0 ? (
        <div className="sig-empty">Bu zaman diliminde kayıtlı sinyal bulunamadı.</div>
      ) : (
        <div className="sig-table-wrap">
          <table className="sig-table">
            <thead>
              <tr>
                <th className="sig-th-sort" onClick={() => handleSort('ticker')}>Hisse{sortIcon('ticker')}</th>
                {ALL_TF_COLS.map(col => (
                  <th key={col.key} className={`sig-th-sort sig-th-tf ${tfTab === col.key || (tfTab === 'genel' && col.key === 'score') ? 'sig-th-active' : ''}`}
                    onClick={() => handleSort(col.scoreKey)}>
                    {col.label}{sortIcon(col.scoreKey)}
                  </th>
                ))}
                <th className="sig-th-sort" onClick={() => handleSort('price')}>Fiyat{sortIcon('price')}</th>
                <th className="sig-th-sort" onClick={() => handleSort('sl')}>Zarar Kes{sortIcon('sl')}</th>
                <th className="sig-th-sort" onClick={() => handleSort('tp')}>Hedef 1{sortIcon('tp')}</th>
                <th className="sig-th-sort" onClick={() => handleSort('tp2')}>Hedef 2{sortIcon('tp2')}</th>
                <th className="sig-th-sort" onClick={() => handleSort('created_at')}>Tarih{sortIcon('created_at')}</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((s, i) => (
                <tr key={i}>
                  <td className="sig-ticker sig-ticker-btn" onClick={() => onTickerClick?.(s.ticker)}>{s.ticker}</td>
                  {ALL_TF_COLS.map(col => {
                    const act = s[col.actionKey]
                    const sc  = s[col.scoreKey]
                    const isActive = tfTab === col.key || (tfTab === 'genel' && col.key === 'score')
                    return (
                      <td key={col.key} className={`sig-tf-cell ${isActive ? 'sig-tf-cell-active' : ''}`}>
                        <span className={`sig-badge sig-badge-sm ${ACTION_CLS[act] || ''}`}>{act || '—'}</span>
                        <span className="sig-tf-score">{sc != null ? sc.toFixed(1) : '—'}</span>
                      </td>
                    )
                  })}
                  <td>₺{s.price?.toFixed(2)}</td>
                  <td className="sig-sl">{s.sl ? `₺${s.sl?.toFixed(2)}` : '—'}</td>
                  <td className="sig-tp">{s.tp ? `₺${s.tp?.toFixed(2)}` : '—'}</td>
                  <td className="sig-tp">{s.tp2 ? `₺${s.tp2?.toFixed(2)}` : '—'}</td>
                  <td className="sig-date">{new Date(s.created_at).toLocaleString('tr-TR')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
