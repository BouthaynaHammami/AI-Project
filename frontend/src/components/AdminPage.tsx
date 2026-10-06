import { ArrowLeft, RefreshCw, ShieldAlert } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { getApiError } from '../services/api'
import {
  getAdminStats,
  getAdminUsers,
  updateAdminUser,
  type AdminStats,
  type AdminUser,
} from '../services/usageService'

type Props = {
  onBack: () => void
}

function percent(value: number) {
  return `${(value * 100).toFixed(1)} %`
}

function date(value: string | null) {
  return value
    ? new Date(value).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' })
    : 'Aucune activité'
}

export function AdminPage({ onBack }: Props) {
  const [users, setUsers] = useState<AdminUser[]>([])
  const [quotaDrafts, setQuotaDrafts] = useState<Record<number, string>>({})
  const [stats, setStats] = useState<AdminStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [savingId, setSavingId] = useState<number | null>(null)
  const [error, setError] = useState('')
  const [forbidden, setForbidden] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [nextUsers, nextStats] = await Promise.all([getAdminUsers(), getAdminStats()])
      setUsers(nextUsers)
      setStats(nextStats)
      setForbidden(false)
    } catch (loadError) {
      const axiosError = loadError as { response?: { status?: number } }
      setForbidden(axiosError.response?.status === 403)
      setError(getApiError(loadError))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const updateUser = async (userId: number, patch: { monthly_quota?: number; is_active?: boolean }) => {
    setSavingId(userId)
    setError('')
    try {
      const updated = await updateAdminUser(userId, patch)
      setUsers((current) => current.map((user) => user.id === userId ? updated : user))
      if (patch.monthly_quota !== undefined) {
        setQuotaDrafts((current) => {
          const next = { ...current }
          delete next[userId]
          return next
        })
      }
    } catch (updateError) {
      setError(getApiError(updateError))
      if (patch.monthly_quota !== undefined) {
        setQuotaDrafts((current) => {
          const next = { ...current }
          delete next[userId]
          return next
        })
      }
    } finally {
      setSavingId(null)
    }
  }

  const maxDaily = Math.max(1, ...(stats?.daily.map((item) => item.analyses) ?? []))

  return (
    <main className="admin-page">
      <header className="admin-header">
        <button type="button" className="admin-back" onClick={onBack}><ArrowLeft size={16} /> Retour</button>
        <div>
          <span className="workspace-kicker">GESTION DE LA PLATEFORME</span>
          <h1>Administration</h1>
        </div>
        <button type="button" className="admin-refresh" onClick={() => void load()} disabled={loading}>
          <RefreshCw size={15} /> Actualiser
        </button>
      </header>
      {error && (
        <div className="admin-error" role="alert">
          <ShieldAlert size={17} />
          <span>{forbidden ? 'Accès réservé aux administrateurs.' : error}</span>
          {!forbidden && <button type="button" onClick={() => void load()}>Réessayer</button>}
        </div>
      )}
      {loading && <p className="admin-loading">Chargement des données d’administration…</p>}
      {!loading && !error && stats && (
        <>
          <section className="admin-stat-grid" aria-label="Statistiques globales">
            <article><span>Analyses aujourd’hui</span><strong>{stats.analyses_today.toLocaleString('fr-FR')}</strong></article>
            <article><span>Taux d’erreur (14 jours)</span><strong>{percent(stats.error_rate)}</strong></article>
            <article><span>Taux de 👍</span><strong>{percent(stats.like_rate)}</strong></article>
            <article><span>Tokens consommés (14 jours)</span><strong>{(stats.tokens_in + stats.tokens_out).toLocaleString('fr-FR')}</strong></article>
          </section>
          <section className="admin-chart-card">
            <h2>Analyses par jour · 14 derniers jours</h2>
            <div className="admin-bars" role="img" aria-label="Graphique du nombre d’analyses par jour">
              {stats.daily.map((item) => (
                <div className="admin-bar-column" key={item.date} title={`${item.date} : ${item.analyses} analyses`}>
                  <span className="admin-bar-value">{item.analyses}</span>
                  <span className="admin-bar" style={{ height: `${Math.max(3, item.analyses / maxDaily * 100)}%` }} />
                  <small>{new Date(`${item.date}T00:00:00`).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' })}</small>
                </div>
              ))}
            </div>
          </section>
          <section className="admin-users-card">
            <div className="admin-users-heading"><h2>Utilisateurs</h2><span>{users.length} comptes</span></div>
            <div className="admin-table-wrap">
              <table>
                <thead>
                  <tr><th>Utilisateur</th><th>Analyses</th><th>Tokens</th><th>Activité récente</th><th>Quota mensuel</th><th>État</th></tr>
                </thead>
                <tbody>
                  {users.map((user) => (
                    <tr key={user.id}>
                      <td><strong>{user.name}</strong><small>{user.email}{user.role === 'admin' ? ' · Admin' : ''}</small></td>
                      <td>{user.analyses_used}</td>
                      <td>{(user.tokens_in + user.tokens_out).toLocaleString('fr-FR')}</td>
                      <td>{date(user.last_activity)}</td>
                      <td>
                        <input
                          aria-label={`Quota mensuel pour ${user.email}`}
                          type="number"
                          min={0}
                          max={1000000}
                          value={quotaDrafts[user.id] ?? String(user.monthly_quota)}
                          disabled={savingId === user.id}
                          onChange={(event) => {
                            setQuotaDrafts((current) => ({ ...current, [user.id]: event.target.value }))
                          }}
                          onBlur={(event) => {
                            const value = Number(event.currentTarget.value)
                            if (Number.isInteger(value) && value >= 0 && value <= 1_000_000 && value !== user.monthly_quota) {
                              void updateUser(user.id, { monthly_quota: value })
                            } else {
                              setQuotaDrafts((current) => {
                                const next = { ...current }
                                delete next[user.id]
                                return next
                              })
                            }
                          }}
                        />
                      </td>
                      <td>
                        <button
                          type="button"
                          className={`admin-status-toggle${user.is_active ? ' is-active' : ''}`}
                          disabled={savingId === user.id}
                          onClick={() => void updateUser(user.id, { is_active: !user.is_active })}
                        >
                          {user.is_active ? 'Actif' : 'Désactivé'}
                        </button>
                      </td>
                    </tr>
                  ))}
                  {!users.length && <tr><td colSpan={6}>Aucun utilisateur trouvé.</td></tr>}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </main>
  )
}
