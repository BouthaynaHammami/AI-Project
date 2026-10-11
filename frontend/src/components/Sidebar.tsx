import { BarChart3, ChevronDown, LogOut, Plus, Settings, UserRound } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { HistoryEntry } from '../types'
import { groupByDate } from '../utils/history'
import { HistoryGroup } from './HistoryGroup'
import { HistorySearch } from './HistorySearch'
import { UndoToast } from './UndoToast'

type Props = {
  userName: string
  profilePhoto: string
  history: HistoryEntry[]
  activeId: number
  query?: string
  favoriteOnly?: boolean
  loading?: boolean
  hasMore?: boolean
  error?: string
  undoEntry?: HistoryEntry | null
  cascadePrompt?: { item?: HistoryEntry } | null
  onNew: () => void
  onHistory: (id: number) => void
  onSettings: () => void
  onLogout: () => void
  onSearch?: (query: string, favoriteOnly: boolean) => void
  onLoadMore?: () => void
  onRetry?: () => void
  onRename?: (item: HistoryEntry, title: string) => Promise<void>
  onToggleFavorite?: (item: HistoryEntry) => Promise<void>
  onRemove?: (item: HistoryEntry) => Promise<void>
  onUndoRemove?: () => void
  onConfirmCascade?: () => void
  onCancelCascade?: () => void
}

export function Sidebar({
  userName, profilePhoto, history, activeId, query = '', favoriteOnly = false,
  loading = false, hasMore = false, error = '', undoEntry = null,
  cascadePrompt = null, onNew, onHistory, onSettings, onLogout, onSearch,
  onLoadMore, onRetry, onRename, onToggleFavorite, onRemove, onUndoRemove,
  onConfirmCascade, onCancelCascade,
}: Props) {
  const [historyOpen, setHistoryOpen] = useState(false)
  const [search, setSearch] = useState(query)
  const [favorites, setFavorites] = useState(favoriteOnly)
  const [editingId, setEditingId] = useState<number | null>(null)
  const searchRef = useRef<HTMLInputElement>(null)

  useEffect(() => setSearch(query), [query])
  useEffect(() => setFavorites(favoriteOnly), [favoriteOnly])
  useEffect(() => {
    if (!onSearch) return
    const timer = window.setTimeout(() => onSearch(search, favorites), 300)
    return () => window.clearTimeout(timer)
  }, [favorites, onSearch, search])

  const groups = groupByDate(history)
  const groupTitles = [
    ['today', 'Aujourd’hui'],
    ['yesterday', 'Hier'],
    ['thisWeek', 'Cette semaine'],
    ['older', 'Plus ancien'],
  ] as const

  return (
    <aside className="sidebar">
      <div className="sidebar-top"><div className="brand-mark"><BarChart3 size={18} /></div><span>AI Data <b>Analyst</b></span></div>
      <div className="sidebar-user-card">
        <div className="sidebar-user-avatar">{profilePhoto ? <img src={profilePhoto} alt="Photo de profil" /> : <UserRound size={15} />}</div>
        <div className="sidebar-user-meta"><strong>{userName}</strong></div>
      </div>
      <button className="new-analysis" onClick={onNew}><Plus size={17} /> Nouvelle analyse</button>
      {onSearch && (
        <HistorySearch
          value={search}
          favoriteOnly={favorites}
          inputRef={searchRef}
          onChange={setSearch}
          onToggleFavorites={() => setFavorites((current) => !current)}
        />
      )}
      <button className={`history-heading ${historyOpen ? 'history-heading-open' : ''}`} onClick={() => setHistoryOpen((open) => !open)} aria-expanded={historyOpen}>
        <span>Historique</span>
        <span className="history-heading-right"><span className="history-count">{history.length}</span><ChevronDown size={14} /></span>
      </button>
      {historyOpen && (
        <div className="history-list">
          {history.length ? groupTitles.map(([key, title]) => (
            <HistoryGroup
              key={key}
              title={title}
              items={groups[key]}
              activeId={activeId}
              query={search}
              editingId={editingId}
              onHistory={onHistory}
              onStartRename={setEditingId}
              onRename={async (item, nextTitle) => {
                await onRename?.(item, nextTitle)
                setEditingId(null)
              }}
              onCancelRename={() => setEditingId(null)}
              onToggleFavorite={(item) => onToggleFavorite?.(item) ?? Promise.resolve()}
              onRemove={(item) => onRemove?.(item) ?? Promise.resolve()}
            />
          )) : <p className="history-empty">{loading ? 'Chargement de l’historique…' : 'Aucune analyse enregistrée.'}</p>}
          {error && <p className="history-error" role="alert">{error}<button type="button" onClick={onRetry}>Réessayer</button></p>}
          {hasMore && <button type="button" onClick={onLoadMore} disabled={loading}>{loading ? 'Chargement…' : 'Charger plus'}</button>}
        </div>
      )}
      {cascadePrompt && (
        <div role="alertdialog" aria-label="Supprimer la conversation">
          <p>Cette action supprimera toute la conversation.</p>
          <button type="button" onClick={onConfirmCascade}>Supprimer</button>
          <button type="button" onClick={onCancelCascade}>Annuler</button>
        </div>
      )}
      {undoEntry && <UndoToast message="Analyse supprimée." onUndo={() => onUndoRemove?.()} />}
      <div className="sidebar-bottom">
        <button className="sidebar-action" onClick={onSettings}><Settings size={17} /> Paramètres</button>
        <button className="sidebar-action logout" onClick={onLogout}><LogOut size={17} /> Déconnexion</button>
      </div>
    </aside>
  )
}
