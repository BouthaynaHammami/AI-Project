import { BarChart3, Database, Download, FileImage, FileSpreadsheet, FileText, Hash, MessageSquare } from 'lucide-react'
import { useRef, useState } from 'react'
import { ChatWindow } from './ChatWindow'
import { DataPreviewTable } from './DataPreviewTable'
import { SuggestedQuestions } from './SuggestedQuestions'
import { ChartRenderer } from './ChartRenderer'
import { ShareControls } from './ShareControls'
import { getApiError } from '../services/api'
import { exportAnalysis } from '../services/analysisService'
import type { ChartConfig, Message } from '../types'
import type { DatasetPreview } from '../services/fileService'

type Props = {
  datasets: DatasetPreview[]
  conversationId?: number | null
  firstQuestion: string
  messages: Message[]
  isAnalyzing: boolean
  chartConfig: string | null
  onAsk: (question: string, datasetIds?: number[]) => void
  onAddFiles: (files: File[]) => Promise<void>
  onNewConversation?: () => void
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

export function AnalysisPage({ datasets, conversationId, firstQuestion, messages, isAnalyzing, chartConfig, onAsk, onAddFiles, onNewConversation }: Props) {
  const chartRef = useRef<HTMLDivElement>(null)
  const [exportMenuOpen, setExportMenuOpen] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [exportError, setExportError] = useState('')
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
  const latestAnalysisId = [...messages].reverse().find(
    (message) => message.role === 'assistant' && message.analysisId != null,
  )?.analysisId

  const downloadBlob = (blob: Blob, filename: string) => {
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  }

  const exportDocument = async (format: 'pdf' | 'xlsx') => {
    if (latestAnalysisId == null || exporting) return
    setExporting(true)
    setExportError('')
    try {
      const file = await exportAnalysis(latestAnalysisId, format)
      downloadBlob(file.blob, file.filename)
      setExportMenuOpen(false)
    } catch (error) {
      setExportError(getApiError(error))
    } finally {
      setExporting(false)
    }
  }

  const exportChartPng = async () => {
    const svg = chartRef.current?.querySelector('svg')
    if (!svg) {
      setExportError('Aucun graphique disponible pour l’export PNG.')
      return
    }
    setExporting(true)
    setExportError('')
    try {
      const clonedSvg = svg.cloneNode(true) as SVGSVGElement
      clonedSvg.setAttribute('xmlns', 'http://www.w3.org/2000/svg')
      const svgBlob = new Blob([new XMLSerializer().serializeToString(clonedSvg)], {
        type: 'image/svg+xml;charset=utf-8',
      })
      const svgUrl = URL.createObjectURL(svgBlob)
      try {
        const image = new Image()
        const imageReady = new Promise<void>((resolve, reject) => {
          image.onload = () => resolve()
          image.onerror = () => reject(new Error('Impossible de convertir le graphique en image.'))
        })
        image.src = svgUrl
        await imageReady
        const bounds = svg.getBoundingClientRect()
        const scale = 2
        const canvas = document.createElement('canvas')
        canvas.width = Math.max(1, Math.round((bounds.width || 800) * scale))
        canvas.height = Math.max(1, Math.round((bounds.height || 450) * scale))
        const context = canvas.getContext('2d')
        if (!context) throw new Error('Le navigateur ne permet pas de créer cette image.')
        context.fillStyle = '#FFFFFF'
        context.fillRect(0, 0, canvas.width, canvas.height)
        context.drawImage(image, 0, 0, canvas.width, canvas.height)
        const png = await new Promise<Blob>((resolve, reject) => {
          canvas.toBlob((blob) => {
            if (blob) resolve(blob)
            else reject(new Error('Impossible de générer le fichier PNG.'))
          }, 'image/png')
        })
        downloadBlob(png, `analyse-${latestAnalysisId ?? conversationId ?? 'graphique'}.png`)
      } finally {
        URL.revokeObjectURL(svgUrl)
      }
      setExportMenuOpen(false)
    } catch (error) {
      setExportError(getApiError(error))
    } finally {
      setExporting(false)
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
        <div className="analysis-page-actions">
          <span className="success-badge">● Dataset connecté</span>
          {latestAnalysisId != null && <ShareControls analysisId={latestAnalysisId} />}
          <div className="export-menu">
            <button
              type="button"
              className="export-menu-trigger"
              aria-expanded={exportMenuOpen}
              aria-haspopup="menu"
              onClick={() => setExportMenuOpen((open) => !open)}
            >
              <Download size={15} /> Exporter
            </button>
            {exportMenuOpen && (
              <div className="export-menu-options" role="menu" aria-label="Formats d’export">
                <button type="button" role="menuitem" disabled={exporting || latestAnalysisId == null} onClick={() => void exportDocument('pdf')}>
                  <FileText size={14} /> PDF
                </button>
                <button type="button" role="menuitem" disabled={exporting || latestAnalysisId == null} onClick={() => void exportDocument('xlsx')}>
                  <FileSpreadsheet size={14} /> Excel
                </button>
                <button type="button" role="menuitem" disabled={exporting || !chart} onClick={() => void exportChartPng()}>
                  <FileImage size={14} /> PNG du graphique
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
      {exportError && <p className="export-error" role="alert">{exportError}</p>}

      {!firstQuestion.trim() && !messages.some((message) => message.role === 'user') && (
        <SuggestedQuestions
          datasetIds={datasets.map((dataset) => dataset.dataset_id)}
          onSelect={(question) => onAsk(question, datasets.map((dataset) => dataset.dataset_id))}
        />
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
                  <h3>{chart?.title ?? 'Graphique en attente de l’analyse IA'}</h3>
                </div>
              </div>
              {chart ? (
                <div ref={chartRef} className="chart-export-source"><ChartRenderer config={chart} /></div>
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
              <p>{[...messages].reverse().find((message) => message.role === 'assistant')?.content ?? 'Aucun résultat enregistré.'}</p>
            </section>
          </div>
        </>
      )}

      {tabularDatasets.length > 0 && <DataPreviewTable datasets={tabularDatasets} />}
      <ChatWindow
        messages={messages}
        isAnalyzing={isAnalyzing}
        conversationId={conversationId}
        onAsk={(question) => onAsk(question, datasets.map((dataset) => dataset.dataset_id))}
        onAddFiles={onAddFiles}
        onNewConversation={onNewConversation}
      />
    </div>
  )
}