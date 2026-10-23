import { ChevronDown, LogOut, Menu, Plus, Settings, UserRound, X } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
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
  query?: string
  favoriteOnly?: boolean
  loading?: boolean
  hasMore?: boolean
  error?: string
  undoEntry?: HistoryEntry | null
  cascadePrompt?: { item: HistoryEntry; analysisCount: number } | null
  onNew: () => void
  onHistory: (item: HistoryEntry) => void
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
  const [historyOpen, setHistoryOpen] = useState(true)
  const [search, setSearch] = useState(query)
  const [favorites, setFavorites] = useState(favoriteOnly)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [mobileOpen, setMobileOpen] = useState(false)
  const searchRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)
  const sentinelRef = useRef<HTMLDivElement>(null)

  useEffect(() => setSearch(query), [query])
  useEffect(() => setFavorites(favoriteOnly), [favoriteOnly])
  useEffect(() => {
    if (!onSearch) return
    const timer = window.setTimeout(() => onSearch(search, favorites), 300)
    return () => window.clearTimeout(timer)
  }, [favorites, onSearch, search])

  useEffect(() => {
    const onShortcut = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        searchRef.current?.focus()
      }
      if (event.key === 'Escape' && mobileOpen) setMobileOpen(false)
    }
    window.addEventListener('keydown', onShortcut)
    return () => window.removeEventListener('keydown', onShortcut)
  }, [mobileOpen])

  useEffect(() => {
    const node = sentinelRef.current
    const root = listRef.current
    if (!node || !root || !hasMore || !onLoadMore) return
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting && !loading) onLoadMore()
    }, { root, rootMargin: '120px' })
    observer.observe(node)
    return () => observer.disconnect()
  }, [hasMore, loading, onLoadMore])

  const visibleHistory = useMemo(() => history.filter((item) => {
    if (favorites && !item.isFavorite) return false
    if (!search.trim()) return true
    const term = search.trim().toLocaleLowerCase()
    return [item.title, item.question, item.answer, item.file].some((value) => value?.toLocaleLowerCase().includes(term))
  }), [favorites, history, search])
  const groups = groupByDate(visibleHistory)
  const favoriteItems = visibleHistory.filter((item) => item.isFavorite)
  const groupTitles = [
    ['today', 'Aujourd’hui'],
    ['yesterday', 'Hier'],
    ['thisWeek', 'Cette semaine'],
    ['older', 'Plus ancien'],
  ] as const

  return (
    <>
    <button className="sidebar-mobile-toggle" aria-label="Ouvrir le menu" aria-expanded={mobileOpen} onClick={() => setMobileOpen(true)}><Menu size={20} /></button>
    {mobileOpen && <button className="sidebar-mobile-overlay" aria-label="Fermer le menu" onClick={() => setMobileOpen(false)} />}
    <aside className={`sidebar${mobileOpen ? ' sidebar-mobile-open' : ''}`} role="navigation" aria-label="Navigation principale">
      <div className="sidebar-top">
        <img className="sidebar-logo" src={logoUrl} alt="" />
        <span>AI Data <b>Analyst</b></span>
        <button className="sidebar-mobile-close" aria-label="Fermer le menu" onClick={() => setMobileOpen(false)}><X size={18} /></button>
      </div>
      <div className="sidebar-user-card">
        <div className="sidebar-user-avatar">{profilePhoto ? <img src={profilePhoto} alt="Photo de profil" /> : <UserRound size={15} />}</div>
        <div className="sidebar-user-meta"><strong>{userName}</strong></div>
      </div>
      <button className="new-analysis" onClick={() => { onNew(); setMobileOpen(false) }}><Plus size={17} /> Nouvelle analyse</button>
      {onSearch && (
        <HistorySearch
          value={search}
          favoriteOnly={favorites}
          inputRef={searchRef}
          onChange={setSearch}
          onToggleFavorites={() => setFavorites((current) => !current)}
        />
      )}
      <div className="sidebar-history-scroll" ref={listRef}>
      <button className={`history-heading ${historyOpen ? 'history-heading-open' : ''}`} onClick={() => setHistoryOpen((open) => !open)} aria-expanded={historyOpen}>
        <span>Historique</span>
        <span className="history-heading-right"><span className="history-count">{visibleHistory.length}</span><ChevronDown size={14} /></span>
      </button>
      {historyOpen && (
        <div className="history-list">
          {favoriteItems.length > 0 && <HistoryGroup
            title="Favoris"
            items={favoriteItems}
            activeId={activeId}
            query={search}
            editingId={editingId}
            onHistory={(item) => { onHistory(item); setMobileOpen(false) }}
            onStartRename={setEditingId}
            onRename={async (item, nextTitle) => { await onRename?.(item, nextTitle); setEditingId(null) }}
            onCancelRename={() => setEditingId(null)}
            onToggleFavorite={(item) => onToggleFavorite?.(item) ?? Promise.resolve()}
            onRemove={(item) => onRemove?.(item) ?? Promise.resolve()}
          />}
          {loading && visibleHistory.length === 0 ? <div className="history-skeletons" aria-label="Chargement de l’historique">
            {Array.from({ length: 5 }, (_, index) => <span key={index} />)}
          </div> : visibleHistory.length ? groupTitles.map(([key, title]) => (
            <HistoryGroup
              key={key}
              title={title}
              items={groups[key]}
              activeId={activeId}
              query={search}
              editingId={editingId}
              onHistory={(item) => { onHistory(item); setMobileOpen(false) }}
              onStartRename={setEditingId}
              onRename={async (item, nextTitle) => {
                await onRename?.(item, nextTitle)
                setEditingId(null)
              }}
              onCancelRename={() => setEditingId(null)}
              onToggleFavorite={(item) => onToggleFavorite?.(item) ?? Promise.resolve()}
              onRemove={(item) => onRemove?.(item) ?? Promise.resolve()}
            />
          )) : <p className="history-empty">{loading ? 'Chargement de l’historique…' : search || favorites ? `Aucun résultat pour « ${search} »` : 'Aucune analyse.'}</p>}
          {error && <p className="history-error" role="alert">{error}<button type="button" onClick={onRetry}>Réessayer</button></p>}
          {hasMore && <button type="button" onClick={onLoadMore} disabled={loading}>{loading ? 'Chargement…' : 'Charger plus'}</button>}
          {hasMore && <div ref={sentinelRef} className="history-pagination-sentinel" aria-hidden="true" />}
        </div>
      )}
      </div>
      {cascadePrompt && (
        <div role="alertdialog" aria-label="Supprimer la conversation">
          <p>{cascadePrompt.analysisCount} analyses utilisent ce fichier. Supprimer aussi ?</p>
          <button type="button" onClick={onConfirmCascade}>Supprimer</button>
          <button type="button" onClick={onCancelCascade}>Annuler</button>
        </div>
      )}
      {undoEntry && <UndoToast message={undoEntry.kind === 'import' ? 'Fichier supprimé.' : 'Analyse supprimée.'} onUndo={() => onUndoRemove?.()} />}
      <div className="sidebar-bottom">
        <button className="sidebar-action" onClick={() => { onSettings(); setMobileOpen(false) }}><Settings size={17} /> Paramètres</button>
        <button className="sidebar-action logout" onClick={() => { onLogout(); setMobileOpen(false) }}><LogOut size={17} /> Déconnexion</button>
      </div>
    </aside>
    </>
  )
}
