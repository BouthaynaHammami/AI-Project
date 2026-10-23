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
import { useEffect, useMemo, useState } from 'react'
import { getSuggestions } from '../services/analysisService'
import type { SuggestedQuestion } from '../services/analysisService'

type Props = {
  datasetIds: number[]
  onSelect: (question: string) => void
}

const categoryIcons = {
  classement: ListOrdered,
  evolution: Clock3,
  comparaison: Tags,
  repartition: PieChart,
  qualite: ShieldCheck,
  synthese: ChartNoAxesCombined,
}

export function SuggestedQuestions({ datasetIds, onSelect }: Props) {
  const datasetKey = useMemo(() => datasetIds.join(','), [datasetIds])
  const [suggestions, setSuggestions] = useState<SuggestedQuestion[]>([])
  const [loading, setLoading] = useState(true)
  const [empty, setEmpty] = useState(false)
  const [refreshCount, setRefreshCount] = useState(0)

  useEffect(() => {
    if (!datasetKey) {
      setSuggestions([])
      setEmpty(true)
      setLoading(false)
      return
    }

    const controller = new AbortController()
    setLoading(true)
    setEmpty(false)
    void getSuggestions(
      datasetKey.split(',').map(Number),
      refreshCount > 0,
      controller.signal,
    ).then((response) => {
      setSuggestions(response.suggestions)
      setEmpty(response.suggestions.length === 0)
    }).catch(() => {
      if (!controller.signal.aborted) {
        setSuggestions([])
        setEmpty(true)
      }
    }).finally(() => {
      if (!controller.signal.aborted) setLoading(false)
    })

    return () => controller.abort()
  }, [datasetKey, refreshCount])

  return (
    <section className="suggested-questions" aria-label="Questions suggérées">
      <div className="suggested-questions-heading">
        <div>
          <strong>Questions suggérées</strong>
          <span>Suggestions basées sur la structure de vos données — aucune ligne brute n’est envoyée à l’IA.</span>
        </div>
        <button type="button" className="suggestions-refresh" onClick={() => setRefreshCount((count) => count + 1)} disabled={loading} aria-label="Autres idées">
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
