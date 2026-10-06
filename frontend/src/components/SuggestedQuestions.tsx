import {
  BarChart3,
  ChartNoAxesCombined,
  Clock3,
  ListOrdered,
  PieChart,
  RefreshCw,
  ShieldCheck,
  Tags,
} from 'lucide-react'
import type { SuggestedQuestion } from '../services/analysisService'

type Props = {
  suggestions: SuggestedQuestion[]
  loading: boolean
  onSelect: (question: string) => void
  onRefresh: () => void
  empty?: boolean
}

const categoryIcons = {
  classement: ListOrdered,
  evolution: Clock3,
  comparaison: Tags,
  repartition: PieChart,
  qualite: ShieldCheck,
  synthese: ChartNoAxesCombined,
}

export function SuggestedQuestions({ suggestions, loading, onSelect, onRefresh, empty = false }: Props) {
  return (
    <section className="suggested-questions" aria-label="Questions suggérées">
      <div className="suggested-questions-heading">
        <div>
          <strong>Questions suggérées</strong>
          <span>Suggestions basées sur la structure de vos données — aucune ligne brute n’est envoyée à l’IA.</span>
        </div>
        <button type="button" className="suggestions-refresh" onClick={onRefresh} disabled={loading} aria-label="Autres idées">
          <RefreshCw size={14} className={loading ? 'suggestions-refreshing' : ''} />
          Autres idées
        </button>
      </div>
      {loading ? (
        <div className="suggestions-skeleton" role="status" aria-label="Chargement des suggestions">
          <span /><span /><span />
        </div>
      ) : suggestions.length > 0 ? (
        <div className="suggested-question-list">
          {suggestions.map((suggestion, index) => {
            const Icon = categoryIcons[suggestion.category] ?? BarChart3
            return (
              <button
                type="button"
                className="suggested-question"
                key={`${suggestion.question}-${index}`}
                onClick={() => onSelect(suggestion.question)}
              >
                <Icon size={14} aria-hidden="true" />
                <span>{suggestion.question}</span>
                {suggestion.chart && <small><BarChart3 size={12} /> Graphique</small>}
              </button>
            )
          })}
        </div>
      ) : (
        <p className="suggestions-empty">{empty ? 'Aucune suggestion disponible pour ces fichiers.' : 'Importez un fichier pour obtenir des idées adaptées à vos données.'}</p>
      )}
    </section>
  )
}
