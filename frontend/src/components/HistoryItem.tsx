import { FileImage, FileSpreadsheet, FileText, MessageSquare, MoreHorizontal, Star } from 'lucide-react'
import { memo, useEffect, useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'
import type { HistoryEntry } from '../types'

type Props = {
  item: HistoryEntry
  active?: boolean
  query?: string
  editing?: boolean
  onClick: () => void
  onStartRename: () => void
  onRename: (title: string) => Promise<void>
  onCancelRename: () => void
  onToggleFavorite: () => Promise<void>
  onRemove: () => Promise<void>
}

function HighlightedTitle({ title, query }: { title: string; query: string }) {
  if (!query.trim()) return title
  const escaped = query.trim().replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const parts = title.split(new RegExp(`(${escaped})`, 'ig'))
  return <>{parts.map((part, index) => part.toLocaleLowerCase() === query.trim().toLocaleLowerCase()
    ? <mark key={index}>{part}</mark>
    : part)}</>
}

export const HistoryItem = memo(function HistoryItem({
  item,
  active = false,
  query = '',
  editing = false,
  onClick,
  onStartRename,
  onRename,
  onCancelRename,
  onToggleFavorite,
  onRemove,
}: Props) {
  const [title, setTitle] = useState(item.title || item.question || item.file)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [error, setError] = useState('')
  const skipBlurCommit = useRef(false)
  const extension = item.file.split('.').pop()?.toLowerCase()
  const Icon = item.kind === 'discussion'
    ? MessageSquare
    : extension === 'pdf' || extension === 'doc' || extension === 'docx'
      ? FileText
      : extension === 'png' || extension === 'jpg' || extension === 'jpeg'
        ? FileImage
        : FileSpreadsheet

  useEffect(() => setTitle(item.title || item.question || item.file), [item.title, item.question, item.file])

  const commitRename = async () => {
    const trimmed = title.trim()
    if (!trimmed || trimmed.length > 120) {
      setError('Le titre doit contenir entre 1 et 120 caractères.')
      return
    }
    try {
      await onRename(trimmed)
      setError('')
      onCancelRename()
    } catch {
      setError('Le titre n’a pas pu être enregistré.')
    }
  }

  const onItemKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'F2' && item.kind === 'discussion') {
      event.preventDefault()
      onStartRename()
    } else if (event.key === 'Delete' || event.key === 'Backspace') {
      event.preventDefault()
      setConfirmDelete(true)
    } else if (event.key === 'Enter' && event.target === event.currentTarget) {
      onClick()
    }
  }

  return (
    <div
      className={`history-item ${active ? 'history-item-active' : ''}`}
      role="option"
      aria-selected={active}
      tabIndex={0}
      title={`${item.title || item.question || item.file}\n${item.date ? new Date(item.date).toLocaleString('fr-FR') : ''}\n${item.conversationMessages?.length ?? 1} échange(s)`}
      onKeyDown={onItemKeyDown}
    >
      <button className="history-item-main" onClick={onClick} aria-label={item.title || item.question || item.file}>
        <span className="history-file-icon"><Icon size={15} aria-hidden="true" /></span>
        {editing ? (
          <input
            autoFocus
            aria-label="Nouveau titre"
            maxLength={120}
            value={title}
            onChange={(event) => { setTitle(event.target.value); setError('') }}
            onBlur={() => {
              if (skipBlurCommit.current) {
                skipBlurCommit.current = false
                return
              }
              void commitRename()
            }}
            onKeyDown={(event) => {
              event.stopPropagation()
              if (event.key === 'Enter') { event.preventDefault(); skipBlurCommit.current = true; void commitRename() }
              if (event.key === 'Escape') { event.preventDefault(); skipBlurCommit.current = true; onCancelRename(); setTitle(item.title || item.question || item.file) }
            }}
          />
        ) : (
          <span className="history-item-title">
            <strong><HighlightedTitle title={item.title || item.question || item.file} query={query} /></strong>
          </span>
        )}
      </button>
      <div className="history-item-actions">
        {item.kind === 'discussion' && (
          <button
            className={`history-icon-action history-favorite ${item.isFavorite ? 'is-favorite' : ''}`}
            aria-label={item.isFavorite ? 'Retirer des favoris' : 'Ajouter aux favoris'}
            title={item.isFavorite ? 'Retirer des favoris' : 'Ajouter aux favoris'}
            onClick={() => void onToggleFavorite().catch(() => setError('Le favori n’a pas pu être modifié.'))}
          >
            <Star size={14} fill={item.isFavorite ? 'currentColor' : 'none'} />
          </button>
        )}
        <details className="history-menu">
          <summary aria-label="Actions de l’élément" title="Actions"><MoreHorizontal size={16} /></summary>
          <div className="history-menu-popup">
            {item.kind === 'discussion' && <>
              <button onClick={onStartRename}>Renommer</button>
              <button onClick={() => void onToggleFavorite().catch(() => setError('Le favori n’a pas pu être modifié.'))}>
                {item.isFavorite ? 'Retirer des favoris' : 'Ajouter aux favoris'}
              </button>
            </>}
            <button className="history-delete-action" onClick={() => setConfirmDelete(true)}>Supprimer</button>
          </div>
        </details>
      </div>
      {error && <span className="history-item-error" role="alert">{error}</span>}
      {confirmDelete && (
        <div className="history-delete-confirm" role="group" aria-label="Confirmer la suppression">
          <span>Supprimer cet élément ?</span>
          <button onClick={() => { void onRemove(); setConfirmDelete(false) }}>Supprimer</button>
          <button onClick={() => setConfirmDelete(false)}>Annuler</button>
        </div>
      )}
    </div>
  )
})
