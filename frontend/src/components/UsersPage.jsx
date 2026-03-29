import { useState, useEffect } from 'react'

export default function UsersPage({ onBack, token }) {
  const [users, setUsers]       = useState([])
  const [loading, setLoading]   = useState(true)
  const [newUser, setNewUser]   = useState({ username: '', password: '', is_admin: false })
  const [error, setError]       = useState('')
  const [success, setSuccess]   = useState('')

  const headers = { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` }

  const load = () => {
    setLoading(true)
    fetch('/api/users', { headers })
      .then(r => r.json())
      .then(d => { setUsers(d.users || []); setLoading(false) })
      .catch(() => setLoading(false))
  }

  useEffect(load, [])

  const handleCreate = async (e) => {
    e.preventDefault()
    setError(''); setSuccess('')
    const res  = await fetch('/api/users', { method: 'POST', headers, body: JSON.stringify(newUser) })
    const data = await res.json()
    if (!res.ok) { setError(data.detail); return }
    setSuccess(`${newUser.username} oluşturuldu`)
    setNewUser({ username: '', password: '', is_admin: false })
    load()
  }

  const handleDelete = async (id, username) => {
    if (!confirm(`${username} silinsin mi?`)) return
    setError(''); setSuccess('')
    const res  = await fetch(`/api/users/${id}`, { method: 'DELETE', headers })
    const data = await res.json()
    if (!res.ok) { setError(data.detail); return }
    setSuccess('Kullanıcı silindi')
    load()
  }

  return (
    <div style={{ padding: '24px', maxWidth: 600, margin: '0 auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
        <button onClick={onBack} style={{ background: 'none', border: '1px solid #2a2a3a', color: '#94a3b8', borderRadius: 6, padding: '6px 12px', cursor: 'pointer' }}>← Geri</button>
        <h2 style={{ color: '#f1f5f9', margin: 0 }}>👥 Kullanıcı Yönetimi</h2>
      </div>

      {error   && <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', color: '#f87171', borderRadius: 6, padding: '8px 12px', marginBottom: 12, fontSize: '0.85rem' }}>{error}</div>}
      {success && <div style={{ background: 'rgba(34,197,94,0.1)',  border: '1px solid rgba(34,197,94,0.3)',  color: '#4ade80', borderRadius: 6, padding: '8px 12px', marginBottom: 12, fontSize: '0.85rem' }}>{success}</div>}

      {/* Yeni kullanıcı */}
      <div style={{ background: '#13131a', border: '1px solid #2a2a3a', borderRadius: 10, padding: 20, marginBottom: 24 }}>
        <h3 style={{ color: '#f1f5f9', margin: '0 0 16px', fontSize: '0.9rem' }}>Yeni Kullanıcı Ekle</h3>
        <form onSubmit={handleCreate} style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <input
            placeholder="Kullanıcı adı"
            value={newUser.username}
            onChange={e => setNewUser(p => ({ ...p, username: e.target.value }))}
            required
            style={{ background: '#0d0d14', border: '1px solid #2a2a3a', borderRadius: 6, padding: '8px 10px', color: '#f1f5f9', fontSize: '0.85rem', flex: 1, minWidth: 120 }}
          />
          <input
            type="password"
            placeholder="Şifre"
            value={newUser.password}
            onChange={e => setNewUser(p => ({ ...p, password: e.target.value }))}
            required
            style={{ background: '#0d0d14', border: '1px solid #2a2a3a', borderRadius: 6, padding: '8px 10px', color: '#f1f5f9', fontSize: '0.85rem', flex: 1, minWidth: 120 }}
          />
          <label style={{ color: '#94a3b8', fontSize: '0.82rem', display: 'flex', alignItems: 'center', gap: 4, cursor: 'pointer' }}>
            <input type="checkbox" checked={newUser.is_admin} onChange={e => setNewUser(p => ({ ...p, is_admin: e.target.checked }))} />
            Admin
          </label>
          <button type="submit" style={{ background: '#f59e0b', color: '#0a0a0f', border: 'none', borderRadius: 6, padding: '8px 16px', fontWeight: 600, cursor: 'pointer', fontSize: '0.85rem' }}>Ekle</button>
        </form>
      </div>

      {/* Kullanıcı listesi */}
      <div style={{ background: '#13131a', border: '1px solid #2a2a3a', borderRadius: 10, overflow: 'hidden' }}>
        {loading ? (
          <div style={{ color: '#64748b', padding: 20, textAlign: 'center' }}>Yükleniyor…</div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #2a2a3a' }}>
                {['Kullanıcı Adı', 'Rol', 'Oluşturulma', ''].map(h => (
                  <th key={h} style={{ padding: '10px 16px', color: '#64748b', fontSize: '0.75rem', textAlign: 'left', textTransform: 'uppercase' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {users.map(u => (
                <tr key={u.id} style={{ borderBottom: '1px solid #1a1a24' }}>
                  <td style={{ padding: '10px 16px', color: '#f1f5f9', fontSize: '0.88rem' }}>{u.username}</td>
                  <td style={{ padding: '10px 16px' }}>
                    <span style={{ background: u.is_admin ? 'rgba(245,158,11,0.15)' : 'rgba(100,116,139,0.15)', color: u.is_admin ? '#f59e0b' : '#94a3b8', borderRadius: 4, padding: '2px 8px', fontSize: '0.75rem' }}>
                      {u.is_admin ? 'Admin' : 'Kullanıcı'}
                    </span>
                  </td>
                  <td style={{ padding: '10px 16px', color: '#64748b', fontSize: '0.8rem' }}>{new Date(u.created_at).toLocaleDateString('tr-TR')}</td>
                  <td style={{ padding: '10px 16px' }}>
                    <button onClick={() => handleDelete(u.id, u.username)} style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)', color: '#f87171', borderRadius: 4, padding: '3px 10px', cursor: 'pointer', fontSize: '0.78rem' }}>Sil</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
