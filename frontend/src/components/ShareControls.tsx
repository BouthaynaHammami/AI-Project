import { Check, Copy, Link2, Share2, Trash2, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import {
  createShareLink,
  getShareLinks,
  revokeShareLink,
  type ShareLinkSummary,
} from '../services/analysisService'

type Props = {
  analysisId: number
}

const expiryLabels: Record<1 | 7 | 30, string> = {
  1: '24 heures',
  7: '7 jours',
  30: '30 jours',
}

function formatDate(value: string) {
  return new Date(value).toLocaleString('fr-FR', {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}

export function ShareControls({ analysisId }: Props) {
  const [open, setOpen] = useState(false)
  const [expiresInDays, setExpiresInDays] = useState<1 | 7 | 30>(7)
  const [links, setLinks] = useState<ShareLinkSummary[]>([])
  const [createdUrl, setCreatedUrl] = useState('')
  const [copied, setCopied] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open) {
      setCreatedUrl('')
      setCopied(false)
      return
    }
    let active = true
    setCreatedUrl('')
    setCopied(false)
    setBusy(true)
    setError('')
    getShareLinks(analysisId)
      .then((items) => {
        if (active) setLinks(items)
      })
      .catch(() => {
        if (active) setError('Les liens actifs n’ont pas pu être chargés.')
      })
      .finally(() => {
        if (active) setBusy(false)
      })
    return () => {
      active = false
    }
  }, [analysisId, open])

  const createLink = async () => {
    setBusy(true)
    setError('')
    let token: string
    try {
      const created = await createShareLink(analysisId, expiresInDays)
      token = created.token
    } catch {
      setError('Le lien n’a pas pu être créé. Réessayez.')
      setBusy(false)
      return
    }
    setCreatedUrl(`${window.location.origin}/share/${encodeURIComponent(token)}`)
    setCopied(false)
    try {
      setLinks(await getShareLinks(analysisId))
    } catch {
      setError('Le lien a été créé, mais la liste des liens actifs n’a pas pu être actualisée.')
    }
    setBusy(false)
  }

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(createdUrl)
      setCopied(true)
      setError('')
    } catch {
      setError('La copie a échoué. Sélectionnez le lien pour le copier manuellement.')
    }
  }

  const revokeLink = async (shareId: number) => {
    setBusy(true)
    setError('')
    try {
      await revokeShareLink(analysisId, shareId)
      setLinks((current) => current.filter((link) => link.id !== shareId))
    } catch {
      setError('Le lien n’a pas pu être révoqué.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <button
        type="button"
        className="analysis-share-trigger"
        onClick={() => setOpen(true)}
        aria-haspopup="dialog"
      >
        <Share2 size={15} />
        Partager
      </button>
      {open && (
        <div className="share-modal-backdrop" onMouseDown={(event) => {
          if (event.target === event.currentTarget) setOpen(false)
        }}>
          <section
            className="share-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="share-modal-title"
          >
            <header className="share-modal-heading">
              <div>
                <span className="workspace-kicker">LIEN PUBLIC</span>
                <h2 id="share-modal-title">Partager cette analyse</h2>
              </div>
              <button type="button" aria-label="Fermer" onClick={() => setOpen(false)}>
                <X size={18} />
              </button>
            </header>
            <p className="share-modal-copy">
              Toute personne disposant du lien pourra consulter la question, la réponse et le graphique.
              Le lien peut être révoqué à tout moment.
            </p>
            <div className="share-create-row">
              <label htmlFor="share-expiry">Expiration</label>
              <select
                id="share-expiry"
                value={expiresInDays}
                onChange={(event) => setExpiresInDays(Number(event.target.value) as 1 | 7 | 30)}
              >
                {([1, 7, 30] as const).map((days) => (
                  <option key={days} value={days}>{expiryLabels[days]}</option>
                ))}
              </select>
              <button type="button" onClick={() => void createLink()} disabled={busy}>
                <Link2 size={14} />
                Créer un lien
              </button>
            </div>
            {createdUrl && (
              <div className="share-created-link">
                <label htmlFor="created-share-url">Votre lien (affiché uniquement maintenant)</label>
                <div>
                  <input id="created-share-url" readOnly value={createdUrl} onFocus={(event) => event.currentTarget.select()} />
                  <button type="button" onClick={() => void copyLink()} aria-label="Copier le lien">
                    {copied ? <Check size={15} /> : <Copy size={15} />}
                    {copied ? 'Copié' : 'Copier'}
                  </button>
                </div>
              </div>
            )}
            {error && <p className="share-error" role="alert">{error}</p>}
            <div className="share-active-links">
              <h3>Liens actifs</h3>
              {busy && links.length === 0 ? (
                <p>Chargement…</p>
              ) : links.length === 0 ? (
                <p>Aucun lien actif.</p>
              ) : (
                <ul>
                  {links.map((link) => (
                    <li key={link.id}>
                      <div>
                        <strong>Expire le {formatDate(link.expires_at)}</strong>
                        <span>{link.view_count} consultation{link.view_count === 1 ? '' : 's'}</span>
                      </div>
                      <button
                        type="button"
                        onClick={() => void revokeLink(link.id)}
                        disabled={busy}
                        aria-label={`Révoquer le lien qui expire le ${formatDate(link.expires_at)}`}
                        title="Révoquer"
                      >
                        <Trash2 size={15} />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </section>
        </div>
      )}
    </>
  )
}
