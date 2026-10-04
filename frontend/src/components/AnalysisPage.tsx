import { useEffect, useRef, useState } from 'react'
import { BarChart3, ChevronDown, Database, FileDown, FileText, Hash, ImageDown, MessageSquare } from 'lucide-react'
import { ChatWindow } from './ChatWindow'
import { ChartRenderer } from './ChartRenderer'
import { DataPreviewTable } from './DataPreviewTable'
import { ShareControls } from './ShareControls'
import { SuggestedQuestions } from './SuggestedQuestions'
import type { ChartConfig, Message } from '../types'
import type { DatasetPreview } from '../services/fileService'
import { exportAnalysis, getSuggestions, type SuggestedQuestion } from '../services/analysisService'

type Props = {
  datasets: DatasetPreview[]
  firstQuestion: string
  messages: Message[]
  isAnalyzing: boolean
  chartConfig: string | null
  onAsk: (question: string, datasetIds?: number[]) => void
  onFeedback: (analysisId: number, rating: 1 | -1, comment: string | null) => Promise<void>
  onClearFeedback: (analysisId: number) => Promise<void>
  onNewConversation: () => void
  onAddFiles: (files: File[]) => Promise<void>
}

const formatBytes = (size: number) => {
  if (size < 1024) return `${size} o`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} Ko`
  return `${(size / (1024 * 1024)).toFixed(1)} Mo`
}

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}

async function exportChartPng() {
  const svg = document.querySelector('.dashboard-grid .chart-card .chart-renderer svg')
  if (!(svg instanceof SVGSVGElement)) throw new Error('Aucun graphique à exporter.')

  const serializedSvg = new XMLSerializer().serializeToString(svg)
  const imageUrl = URL.createObjectURL(new Blob([serializedSvg], { type: 'image/svg+xml;charset=utf-8' }))
  try {
    const image = new window.Image()
    await new Promise<void>((resolve, reject) => {
      image.onload = () => resolve()
      image.onerror = () => reject(new Error('Le graphique n’a pas pu être converti en image.'))
      image.src = imageUrl
    })
    const bounds = svg.getBoundingClientRect()
    const width = Math.max(1, Math.round(svg.viewBox.baseVal.width || bounds.width))
    const height = Math.max(1, Math.round(svg.viewBox.baseVal.height || bounds.height))
    const canvas = document.createElement('canvas')
    canvas.width = width
    canvas.height = height
    const context = canvas.getContext('2d')
    if (!context) throw new Error('Le navigateur ne permet pas de créer cette image.')
    context.fillStyle = '#ffffff'
    context.fillRect(0, 0, width, height)
    context.drawImage(image, 0, 0, width, height)
    const png = await new Promise<Blob>((resolve, reject) => {
      canvas.toBlob((blob) => blob ? resolve(blob) : reject(new Error('La création du PNG a échoué.')), 'image/png')
    })
    saveBlob(png, 'graphique-analyse.png')
  } finally {
    URL.revokeObjectURL(imageUrl)
  }
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

export function AnalysisPage({ datasets, firstQuestion, messages, isAnalyzing, chartConfig, onAsk, onFeedback, onClearFeedback, onNewConversation, onAddFiles }: Props) {
  const [suggestions, setSuggestions] = useState<SuggestedQuestion[]>([])
  const [suggestionsLoading, setSuggestionsLoading] = useState(false)
  const [suggestionsUnavailable, setSuggestionsUnavailable] = useState(false)
  const [exportMenuOpen, setExportMenuOpen] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [exportError, setExportError] = useState('')
  const suggestionAbortRef = useRef<AbortController | null>(null)
  const datasetIds = datasets.map((dataset) => dataset.dataset_id)
  const datasetIdsKey = datasetIds.join(',')
  const hasAskedQuestion = Boolean(firstQuestion.trim()) || messages.some((message) => message.role === 'user')
  const latestAnalysisId = [...messages].reverse().find((message) => message.role === 'assistant' && message.analysisId)?.analysisId

  useEffect(() => () => suggestionAbortRef.current?.abort(), [])

  useEffect(() => {
    const controller = new AbortController()
    suggestionAbortRef.current?.abort()
    suggestionAbortRef.current = controller
    setSuggestions([])
    setSuggestionsUnavailable(false)
    if (!datasetIdsKey || hasAskedQuestion) return () => controller.abort()

    setSuggestionsLoading(true)
    getSuggestions(datasetIds, false, controller.signal)
      .then((items) => {
        if (!controller.signal.aborted) setSuggestions(items.suggestions)
      })
      .catch(() => {
        if (!controller.signal.aborted) setSuggestionsUnavailable(true)
      })
      .finally(() => {
        if (!controller.signal.aborted) setSuggestionsLoading(false)
      })
    return () => controller.abort()
  }, [datasetIdsKey, hasAskedQuestion])

  const refreshSuggestions = async () => {
    suggestionAbortRef.current?.abort()
    const controller = new AbortController()
    suggestionAbortRef.current = controller
    setSuggestionsLoading(true)
    setSuggestionsUnavailable(false)
    try {
      const result = await getSuggestions(datasetIds, true, controller.signal)
      if (!controller.signal.aborted) {
        setSuggestions(result.suggestions)
        setSuggestionsUnavailable(result.suggestions.length === 0)
      }
    } catch {
      if (!controller.signal.aborted) {
        setSuggestions([])
        setSuggestionsUnavailable(true)
      }
    } finally {
      if (!controller.signal.aborted) setSuggestionsLoading(false)
    }
  }

  const primary = datasets[0] ?? null
  const tabularDatasets = datasets.filter((dataset) => /\.(csv|xlsx?)$/i.test(dataset.filename))
  let chart: ChartConfig | null = null

  try {
    chart = chartConfig ? JSON.parse(chartConfig) as ChartConfig : null
  } catch {
    chart = null
  }

  const totalRows = tabularDatasets.reduce((sum, dataset) => sum + dataset.row_count, 0)
  const totalColumns = tabularDatasets.reduce((sum, dataset) => sum + dataset.column_count, 0)
  const title = datasets.length > 1
    ? `Analyse de ${datasets.length} fichiers`
    : primary
      ? `Analyse de ${primary.filename}`
      : 'Analyse'
  const documentDatasets = datasets.filter((dataset) => /\.(pdf|docx?)$/i.test(dataset.filename))
  const downloadAnalysis = async (format: 'pdf' | 'xlsx') => {
    if (!latestAnalysisId) return
    setExporting(true)
    setExportError('')
    try {
      const result = await exportAnalysis(latestAnalysisId, format)
      saveBlob(result.blob, result.filename)
      setExportMenuOpen(false)
    } catch {
      setExportError('L’export n’a pas pu être téléchargé. Réessayez.')
    } finally {
      setExporting(false)
    }
  }

  const downloadChart = async () => {
    setExportError('')
    try {
      await exportChartPng()
      setExportMenuOpen(false)
    } catch {
      setExportError('Le graphique n’a pas pu être exporté en PNG.')
    }
  }

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
      {latestAnalysisId && (
        <div className="analysis-export">
          <ShareControls analysisId={latestAnalysisId} />
          <button
            type="button"
            className="analysis-export-trigger"
            aria-expanded={exportMenuOpen}
            onClick={() => setExportMenuOpen((open) => !open)}
            disabled={exporting}
          >
            <FileDown size={15} />
            {exporting ? 'Préparation…' : 'Exporter'}
            <ChevronDown size={13} />
          </button>
          {exportMenuOpen && (
            <div className="analysis-export-menu">
              <button type="button" onClick={() => void downloadAnalysis('pdf')} disabled={exporting}>PDF</button>
              <button type="button" onClick={() => void downloadAnalysis('xlsx')} disabled={exporting}>Excel</button>
              {chart && <button type="button" onClick={() => void downloadChart()} disabled={exporting}><ImageDown size={14} /> PNG du graphique</button>}
            </div>
          )}
          {exportError && <p className="analysis-export-error" role="alert">{exportError}</p>}
        </div>
      )}

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
                <ChartRenderer config={chart} />
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
      {!hasAskedQuestion && (
        <SuggestedQuestions
          suggestions={suggestions}
          loading={suggestionsLoading}
          onSelect={(question) => onAsk(question, datasetIds)}
          onRefresh={() => void refreshSuggestions()}
          empty={suggestionsUnavailable}
        />
      )}
      <ChatWindow
        messages={messages}
        isAnalyzing={isAnalyzing}
        onAsk={(question) => onAsk(question, datasetIds)}
        onFeedback={onFeedback}
        onClearFeedback={onClearFeedback}
        onNewConversation={onNewConversation}
        onAddFiles={onAddFiles}
      />
    </div>
  )
}