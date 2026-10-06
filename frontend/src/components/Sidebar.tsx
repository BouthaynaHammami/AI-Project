import { LogOut, Menu, Plus, Settings, X } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import type { KeyboardEvent as ReactKeyboardEvent } from 'react'
import logoUrl from '../../../ai-data-analyst-icon.jpg'
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
  query: string
  favoriteOnly: boolean
  loading: boolean
  hasMore: boolean
  error: string
  undoEntry: HistoryEntry | null
  cascadePrompt: { entry: HistoryEntry; count: number } | null
  onNew: () => void
  onHistory: (id: number) => void
  onSettings: () => void
  onLogout: () => void
  onSearch: (query: string, favoriteOnly: boolean) => Promise<void>
  onLoadMore: () => void
  onRetry: () => void
  onRename: (item: HistoryEntry, title: string) => Promise<void>
  onToggleFavorite: (item: HistoryEntry) => Promise<void>
  onRemove: (item: HistoryEntry) => Promise<void>
  onUndoRemove: () => void
  onConfirmCascade: () => void
  onCancelCascade: () => void
}

export function Sidebar({
  userName, profilePhoto, history, activeId, query, favoriteOnly, loading, hasMore,
  error, undoEntry, cascadePrompt, onNew, onHistory, onSettings, onLogout, onSearch,
  onLoadMore, onRetry, onRename, onToggleFavorite, onRemove, onUndoRemove,
  onConfirmCascade, onCancelCascade,
}: Props) {
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [searchText, setSearchText] = useState(query)
  const [editingId, setEditingId] = useState<number | null>(null)
  const searchRef = useRef<HTMLInputElement>(null)
  const sentinelRef = useRef<HTMLDivElement>(null)
  const initials = userName
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join('')
    .toUpperCase() || 'U'

  useEffect(() => setSearchText(query), [query])

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      if (searchText !== query) void onSearch(searchText, favoriteOnly)
    }, 300)
    return () => window.clearTimeout(timeout)
  }, [searchText, favoriteOnly, onSearch, query])

  useEffect(() => {
    const onShortcut = (event: globalThis.KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        searchRef.current?.focus()
      }
    }
    window.addEventListener('keydown', onShortcut)
    return () => window.removeEventListener('keydown', onShortcut)
  }, [])

  useEffect(() => {
    if (!sentinelRef.current || !hasMore || loading) return
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) onLoadMore()
    }, { root: document.querySelector('.history-scroll'), rootMargin: '120px' })
    observer.observe(sentinelRef.current)
    return () => observer.disconnect()
  }, [hasMore, loading, onLoadMore])

  const favorites = useMemo(() => history.filter((item) => item.kind === 'discussion' && item.isFavorite), [history])
  const nonFavorites = useMemo(() => history.filter((item) => !favorites.includes(item)), [favorites, history])
  const datedGroups = useMemo(() => groupByDate(nonFavorites), [nonFavorites])
  const groupDefinitions = [
    { id: 'today', title: 'Aujourd’hui', items: datedGroups.today },
    { id: 'yesterday', title: 'Hier', items: datedGroups.yesterday },
    { id: 'week', title: 'Cette semaine', items: datedGroups.thisWeek },
    { id: 'older', title: 'Plus ancien', items: datedGroups.older },
  ]

  const handleSearch = (value: string) => {
    setSearchText(value)
    if (!value) void onSearch('', favoriteOnly)
  }

  const toggleFavorites = () => {
    void onSearch(searchText, !favoriteOnly)
  }

  const onHistoryKeyDown = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    if (!['ArrowDown', 'ArrowUp'].includes(event.key)) return
    const options = Array.from(event.currentTarget.querySelectorAll<HTMLElement>('[role="option"]'))
    if (!options.length) return
    const index = options.indexOf(document.activeElement as HTMLElement)
    const next = event.key === 'ArrowDown'
      ? Math.min(options.length - 1, index + 1)
      : Math.max(0, index < 0 ? 0 : index - 1)
    event.preventDefault()
    options[next].focus()
  }

  const onSelectHistory = (id: number) => {
    onHistory(id)
    setDrawerOpen(false)
  }

  const groupProps = {
    activeId,
    query: searchText,
    editingId,
    onHistory: onSelectHistory,
    onStartRename: setEditingId,
    onRename,
    onCancelRename: () => setEditingId(null),
    onToggleFavorite,
    onRemove,
  }

  return (
    <>
      <button className="sidebar-mobile-toggle" aria-label="Ouvrir la navigation" onClick={() => setDrawerOpen(true)}>
        <Menu size={20} />
      </button>
      {drawerOpen && <button className="sidebar-overlay" aria-label="Fermer la navigation" onClick={() => setDrawerOpen(false)} />}
      <aside className={`sidebar ${drawerOpen ? 'sidebar-drawer-open' : ''}`} aria-label="Navigation principale">
        <div className="sidebar-top">
          <img className="sidebar-logo" src={logoUrl} alt="" />
          <span>AI Data <b>Analyst</b></span>
          <button className="sidebar-close" aria-label="Fermer la navigation" onClick={() => setDrawerOpen(false)}><X size={17} /></button>
        </div>
        <div className="sidebar-user-card">
          <div className="sidebar-user-avatar">
            {profilePhoto ? <img src={profilePhoto} alt="" /> : initials}
          </div>
          <div className="sidebar-user-meta"><strong>{userName}</strong></div>
        </div>
        <button className="new-analysis" onClick={() => { onNew(); setDrawerOpen(false) }}>
          <Plus size={17} /> Nouvelle analyse
        </button>

        <div className="history-search-wrap">
          <HistorySearch
            value={searchText}
            favoriteOnly={favoriteOnly}
            inputRef={searchRef}
            onChange={handleSearch}
            onToggleFavorites={toggleFavorites}
          />
        </div>

        <div className="history-section-heading">
          <span>Historique</span>
        </div>
        <div className="history-scroll" onKeyDown={onHistoryKeyDown}>
          {loading && !history.length && (
            <div className="history-skeleton-list" aria-label="Chargement de l’historique" aria-busy="true">
              {Array.from({ length: 6 }, (_, index) => <span className="history-skeleton" key={index} />)}
            </div>
          )}
          {error && (
            <div className="history-error" role="alert">
              <p>Impossible de charger l’historique.</p>
              <button onClick={onRetry}>Réessayer</button>
            </div>
          )}
          {!loading && !error && history.length === 0 && (
            <div className="history-empty-state">
              <p>{searchText ? `Aucun résultat pour « ${searchText} »` : 'Aucune analyse'}</p>
              {searchText && <button onClick={() => handleSearch('')}>Effacer la recherche</button>}
            </div>
          )}
          <div className="history-list-contents">
            <HistoryGroup {...groupProps} title="Favoris" items={favorites} />
            {groupDefinitions.map((group) => (
                <HistoryGroup
                {...groupProps}
                key={group.id}
                title={group.title}
                items={group.items}
                />
              ))}
              {hasMore && <div ref={sentinelRef} className="history-pagination-sentinel" aria-hidden="true" />}
          </div>
          {loading && history.length > 0 && <span className="history-loading-more">Chargement…</span>}
          {hasMore && (
            <button className="history-load-more" disabled={loading} onClick={onLoadMore}>
              Charger plus
            </button>
          )}
        </div>

        <div className="sidebar-bottom">
          <button className="sidebar-action" onClick={() => { onSettings(); setDrawerOpen(false) }}>
            <Settings size={17} /> Paramètres
          </button>
          <button className="sidebar-action logout" onClick={onLogout}>
            <LogOut size={17} /> Déconnexion
          </button>
        </div>
      </aside>
      {undoEntry && <UndoToast message="Élément supprimé" onUndo={onUndoRemove} />}
      {cascadePrompt && (
        <div className="history-modal-backdrop" role="presentation">
          <section className="history-cascade-modal" role="dialog" aria-modal="true" aria-labelledby="cascade-title">
            <h2 id="cascade-title">Des analyses utilisent ce fichier</h2>
            <p>{cascadePrompt.count} analyse{cascadePrompt.count > 1 ? 's' : ''} utilisent encore ce fichier. Voulez-vous aussi les supprimer ?</p>
            <div>
              <button onClick={onCancelCascade}>Annuler</button>
              <button className="history-delete-action" onClick={onConfirmCascade}>Supprimer aussi</button>
            </div>
          </section>
        </div>
      )}
    </>
  )
}
