import { useState } from 'react'
import './LoginPage.css'

export default function LoginPage({ onLogin }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError]       = useState('')
  const [loading, setLoading]   = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res  = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      })
      const data = await res.json()
      if (!res.ok) { setError(data.detail || 'Giriş başarısız'); return }
      localStorage.setItem('ths_token', data.token)
      localStorage.setItem('ths_user', data.username)
      onLogin(data.token, data.username)
    } catch {
      setError('Sunucuya bağlanılamadı')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-logo">
          <span className="login-logo-icon">◈</span>
          <span className="login-logo-text">THS</span>
          <span className="login-logo-sub">AI Terminal</span>
        </div>
        <form className="login-form" onSubmit={handleSubmit}>
          <div className="login-field">
            <label>Kullanıcı Adı</label>
            <input
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              placeholder="kullanıcı adı"
              autoFocus
              required
            />
          </div>
          <div className="login-field">
            <label>Şifre</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="••••••••"
              required
            />
          </div>
          {error && <div className="login-error">{error}</div>}
          <button className="login-btn" type="submit" disabled={loading}>
            {loading ? 'Giriş yapılıyor…' : 'Giriş Yap'}
          </button>
        </form>
      </div>
    </div>
  )
}
