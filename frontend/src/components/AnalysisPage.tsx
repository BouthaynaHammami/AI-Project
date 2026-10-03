import { BarChart3, Database, FileText, Hash, MessageSquare } from 'lucide-react'
import { ChatWindow } from './ChatWindow'
import { DataPreviewTable } from './DataPreviewTable'
import type { ChartConfig, Message } from '../types'
import type { DatasetPreview } from '../services/fileService'

type Props = {
  datasets: DatasetPreview[]
  firstQuestion: string
  messages: Message[]
  isAnalyzing: boolean
  chartConfig: string | null
  onAsk: (question: string, datasetIds?: number[]) => void
  onAddFiles: (files: File[]) => Promise<void>
}

const formatBytes = (size: number) => {
  if (size < 1024) return `${size} o`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} Ko`
  return `${(size / (1024 * 1024)).toFixed(1)} Mo`
}

const documentSuggestions = [
  {
    label: 'Résumer le document',
    question: 'Résume le contenu du document en français, en mettant en évidence son objectif et ses conclusions.',
  },
  {
    label: 'Extraire les points clés',
    question: 'Extrais les points clés, arguments et conclusions des documents importés sous forme de liste.',
  },
  {
    label: 'Poser une question sur le contenu du document',
    question: 'Formule une question importante sur le contenu des documents importés, puis réponds-y à partir du texte.',
  },
  {
    label: 'Extraire dates, montants et informations importantes',
    question: 'Extrais les dates, montants, noms et autres informations importantes des documents. Présente-les de façon structurée.',
  },
]

export function AnalysisPage({ datasets, firstQuestion, messages, isAnalyzing, chartConfig, onAsk, onAddFiles }: Props) {
  const primary = datasets[0] ?? null
  const tabularDatasets = datasets.filter((dataset) => /\.(csv|xlsx?)$/i.test(dataset.filename))
  let chart: ChartConfig | null = null

  try {
    chart = chartConfig ? JSON.parse(chartConfig) as ChartConfig : null
  } catch {
    chart = null
  }

  if (!chart && tabularDatasets.length > 0) {
    const numericDataset = tabularDatasets.find((dataset) =>
      dataset.column_names.some((column) =>
        dataset.preview.some((row) => typeof row[column] === 'number')
      )
    )
    const numericColumn = numericDataset?.column_names.find((column) =>
      numericDataset.preview.some((row) => typeof row[column] === 'number')
    )

    if (numericDataset && numericColumn) {
      const values = numericDataset.preview
        .map((row) => Number(row[numericColumn]))
        .filter((value) => Number.isFinite(value))
      chart = { title: numericColumn, labels: values.map((_, index) => String(index + 1)), values }
    }
  }

  const maxValue = chart ? Math.max(...chart.values, 1) : 1
  const totalRows = tabularDatasets.reduce((sum, dataset) => sum + dataset.row_count, 0)
  const totalColumns = tabularDatasets.reduce((sum, dataset) => sum + dataset.column_count, 0)
  const title = datasets.length > 1
    ? `Analyse de ${datasets.length} fichiers`
    : primary
      ? `Analyse de ${primary.filename}`
      : 'Analyse'
  const documentDatasets = datasets.filter((dataset) => /\.(pdf|docx?)$/i.test(dataset.filename))

  return (
    <div className="analysis-page">
      <div className="analysis-page-title">
        <div>
          <span className="workspace-kicker">RÉSULTAT DE L’ANALYSE</span>
          <h2>{title}</h2>
          {datasets.length > 1 && (
            <p className="analysis-file-list">{datasets.map((dataset) => dataset.filename).join(' · ')}</p>
          )}
          <p>{firstQuestion || 'Posez une question pour commencer.'}</p>
        </div>
        <span className="success-badge">● Dataset connecté</span>
      </div>

      {documentDatasets.length > 0 && (
        <section className="document-analysis-card" aria-label="Analyse des documents">
          <div className="document-analysis-heading">
            <FileText size={18} />
            <div>
              <span className="section-kicker">DOCUMENT IMPORTÉ</span>
              <h3>{documentDatasets.length === 1 ? 'Que souhaitez-vous analyser ?' : `Analyser ${documentDatasets.length} documents`}</h3>
            </div>
          </div>
          <div className="document-file-list">
            {documentDatasets.map((dataset) => (
              <div className="document-file-info" key={dataset.id}>
                <strong className="document-file-name" title={dataset.filename}>{dataset.filename}</strong>
                <span>{dataset.page_count == null ? 'Nombre de pages indisponible' : `${dataset.page_count} page${dataset.page_count > 1 ? 's' : ''}`}</span>
                {dataset.file_size_bytes != null && <span>{formatBytes(dataset.file_size_bytes)}</span>}
              </div>
            ))}
          </div>
          <div className="document-suggestions">
            {documentSuggestions.map((suggestion) => (
              <button className="document-suggestion" type="button" key={suggestion.label} onClick={() => onAsk(suggestion.question, datasets.map((dataset) => dataset.dataset_id))}>
                {suggestion.label}
              </button>
            ))}
          </div>
        </section>
      )}

      {tabularDatasets.length > 0 && (
        <>
          <div className="metric-grid">
            <div className="metric-card">
              <span><Database size={16} /></span>
              <strong>{totalRows.toLocaleString('fr-FR')}</strong>
              <small>Lignes analysées</small>
            </div>
            <div className="metric-card">
              <span><Hash size={16} /></span>
              <strong>{totalColumns}</strong>
              <small>Colonnes détectées</small>
            </div>
            <div className="metric-card">
              <span><BarChart3 size={16} /></span>
              <strong>{datasets.length}</strong>
              <small>Fichier{datasets.length > 1 ? 's' : ''} analysé{datasets.length > 1 ? 's' : ''}</small>
            </div>
            <div className="metric-card">
              <span><MessageSquare size={16} /></span>
              <strong>{messages.filter((message) => message.role === 'user').length}</strong>
              <small>Questions posées</small>
            </div>
          </div>

          <div className="dashboard-grid">
            <section className="dashboard-card chart-card">
              <div className="dashboard-card-head">
                <div>
                  <span className="section-kicker">VISUALISATION</span>
                  <h3>{chart ? `Evolution de ${chart.title}` : 'Graphique en attente de l’analyse IA'}</h3>
                </div>
              </div>
              {chart ? (
                <div className="saved-chart" aria-label={`Graphique de ${chart.title}`}>
                  {chart.values.map((value, index) => (
                    <div className="saved-chart-bar" key={`${chart?.labels[index] ?? index}-${value}`}>
                      <span style={{ height: `${Math.max((value / maxValue) * 100, 4)}%` }} />
                      <small>{chart?.labels[index]}</small>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="empty-dashboard">
                  <BarChart3 size={28} />
                  <p>Le graphique sera disponible après la première question.</p>
                </div>
              )}
            </section>
            <section className="dashboard-card insight-card">
              <span className="section-kicker">INSIGHT IA</span>
              <h3>Résultat enregistré</h3>
              <p>{messages.find((message) => message.role === 'assistant')?.content ?? 'Aucun résultat enregistré.'}</p>
            </section>
          </div>
        </>
      )}

      {tabularDatasets.length > 0 && <DataPreviewTable datasets={tabularDatasets} />}
      <ChatWindow messages={messages} isAnalyzing={isAnalyzing} onAsk={(question) => onAsk(question, datasets.map((dataset) => dataset.dataset_id))} onAddFiles={onAddFiles} />
    </div>
  )
}