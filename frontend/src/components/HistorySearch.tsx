import { Search, Star, X } from 'lucide-react'
import type { RefObject } from 'react'

type Props = {
  value: string
  favoriteOnly: boolean
  inputRef: RefObject<HTMLInputElement | null>
  onChange: (value: string) => void
  onToggleFavorites: () => void
}

export function HistorySearch({ value, favoriteOnly, inputRef, onChange, onToggleFavorites }: Props) {
  return (
    <div className="history-search-panel" role="search" aria-label="Recherche dans l’historique">
      <div className="history-search-heading">
        <label htmlFor="history-search-input">Rechercher</label>
      </div>
      <div className="history-search">
        <Search className="history-search-icon" size={16} aria-hidden="true" />
        <input
          id="history-search-input"
          ref={inputRef}
          type="text"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder="Titres, questions…"
          aria-label="Rechercher dans l’historique"
          autoComplete="off"
        />
        {value && (
          <button className="history-search-clear" aria-label="Effacer la recherche" onClick={() => onChange('')}>
            <X size={14} />
          </button>
        )}
        <span className="history-search-divider" aria-hidden="true" />
        <button
          className={`history-search-favorites${favoriteOnly ? ' favorite-filter-active' : ''}`}
          aria-label={favoriteOnly ? 'Afficher tout l’historique' : 'Filtrer les favoris'}
          aria-pressed={favoriteOnly}
          title={favoriteOnly ? 'Afficher tout l’historique' : 'Filtrer les favoris'}
          onClick={onToggleFavorites}
        >
          <Star size={15} fill={favoriteOnly ? 'currentColor' : 'none'} />
        </button>
      </div>
    </div>
  )
}
