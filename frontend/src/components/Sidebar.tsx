import { ChevronDown, LogOut, Plus, Settings } from 'lucide-react'
import { useState } from 'react'
import logoUrl from '../../../ai-data-analyst-icon.jpg'
import type { HistoryEntry } from '../types'
import { HistoryItem } from './HistoryItem'

type Props = { userName: string; profilePhoto: string; history: HistoryEntry[]; activeId: number; onNew: () => void; onHistory: (id: number) => void; onSettings: () => void; onLogout: () => void }
export function Sidebar({ userName, profilePhoto, history, activeId, onNew, onHistory, onSettings, onLogout }: Props) {
  const [historyOpen, setHistoryOpen] = useState(false)
  const initials = userName
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join('')
    .toUpperCase() || 'U'

  return (
    <aside className="sidebar">
      <div className="sidebar-top">
        <img className="sidebar-logo" src={logoUrl} alt="" />
        <span>AI Data <b>Analyst</b></span>
      </div>
      <div className="sidebar-user-card">
        <div className="sidebar-user-avatar">
          {profilePhoto ? <img src={profilePhoto} alt="Photo de profil" /> : initials}
        </div>
        <div className="sidebar-user-meta"><strong>{userName}</strong></div>
      </div>
      <button className="new-analysis" onClick={onNew}>
        <Plus size={17} /> Nouvelle analyse
      </button>
      <button
        className={`history-heading ${historyOpen ? 'history-heading-open' : ''}`}
        onClick={() => setHistoryOpen((open) => !open)}
        aria-expanded={historyOpen}
      >
        <span>Historique</span>
        <span className="history-heading-right">
          <span className="history-count">{history.length}</span>
          <ChevronDown size={14} />
        </span>
      </button>
      {historyOpen && (
        <div className="history-list">
          {history.length
            ? history.map((item) => (
                <HistoryItem
                  key={item.id}
                  item={item}
                  active={activeId === item.id}
                  onClick={() => onHistory(item.id)}
                />
              ))
            : <p className="history-empty">Aucune analyse enregistrée.</p>}
        </div>
      )}
      <div className="sidebar-bottom">
        <button className="sidebar-action" onClick={onSettings}>
          <Settings size={17} /> Paramètres
        </button>
        <button className="sidebar-action logout" onClick={onLogout}>
          <LogOut size={17} /> Déconnexion
        </button>
      </div>
    </aside>
  )
}