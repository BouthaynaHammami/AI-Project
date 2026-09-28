import { BarChart3, Database, Hash, MessageSquare } from 'lucide-react'
import { ChatWindow } from './ChatWindow'
import { DataPreviewTable } from './DataPreviewTable'
import type { ChartConfig, Message } from '../types'
import type { DatasetPreview } from '../services/fileService'

type Props = { datasets: DatasetPreview[]; firstQuestion: string; messages: Message[]; chartConfig: string | null; onAsk: (question: string) => void }

export function AnalysisPage({ datasets, firstQuestion, messages, chartConfig, onAsk }: Props) {
  const primary = datasets[0] ?? null
  let chart: ChartConfig | null = null
  try { chart = chartConfig ? JSON.parse(chartConfig) as ChartConfig : null } catch { chart = null }
  if (!chart && primary) {
    const numericColumn = primary.column_names.find((column) => primary.preview.some((row) => typeof row[column] === 'number'))
    if (numericColumn) {
      const values = primary.preview.map((row) => Number(row[numericColumn])).filter((value) => Number.isFinite(value))
      chart = { title: numericColumn, labels: values.map((_, index) => String(index + 1)), values }
    }
  }
  const maxValue = chart ? Math.max(...chart.values, 1) : 1
  const totalRows = datasets.reduce((sum, d) => sum + d.row_count, 0)
  const totalColumns = datasets.reduce((sum, d) => sum + d.column_count, 0)
  const title = datasets.length > 1 ? `Analyse de ${datasets.length} fichiers` : primary ? `Analyse de ${primary.filename}` : 'Analyse'

  return <div className="analysis-page"><div className="analysis-page-title"><div><span className="workspace-kicker">RÉSULTAT DE L’ANALYSE</span><h2>{title}</h2>{datasets.length > 1 && <p className="analysis-file-list">{datasets.map((d) => d.filename).join(' · ')}</p>}<p>{firstQuestion || 'Posez une question pour commencer.'}</p></div><span className="success-badge">● Dataset connecté</span></div>{datasets.length ? <><div className="metric-grid"><div className="metric-card"><span><Database size={16} /></span><strong>{totalRows.toLocaleString('fr-FR')}</strong><small>Lignes analysées</small></div><div className="metric-card"><span><Hash size={16} /></span><strong>{totalColumns}</strong><small>Colonnes détectées</small></div><div className="metric-card"><span><BarChart3 size={16} /></span><strong>{datasets.length}</strong><small>Fichier{datasets.length > 1 ? 's' : ''} analysé{datasets.length > 1 ? 's' : ''}</small></div><div className="metric-card"><span><MessageSquare size={16} /></span><strong>{messages.filter((message) => message.role === 'user').length}</strong><small>Questions posées</small></div></div><div className="dashboard-grid"><section className="dashboard-card chart-card"><div className="dashboard-card-head"><div><span className="section-kicker">VISUALISATION</span><h3>{chart ? `Evolution de ${chart.title}` : 'Graphique en attente de l’analyse IA'}</h3></div></div>{chart ? <div className="saved-chart" aria-label={`Graphique de ${chart.title}`}>{chart.values.map((value, index) => <div className="saved-chart-bar" key={`${chart?.labels[index] ?? index}-${value}`}><span style={{ height: `${Math.max((value / maxValue) * 100, 4)}%` }} /><small>{chart?.labels[index]}</small></div>)}</div> : <div className="empty-dashboard"><BarChart3 size={28} /><p>Le graphique sera disponible après la première question.</p></div>}</section><section className="dashboard-card insight-card"><span className="section-kicker">INSIGHT IA</span><h3>Résultat enregistré</h3><p>{messages.find((message) => message.role === 'assistant')?.content ?? 'Aucun résultat enregistré.'}</p></section></div></> : <div className="empty-dashboard large"><Database size={30} /><p>Sélectionnez un dataset réel dans l’historique ou importez un fichier.</p></div>}<DataPreviewTable datasets={datasets} /><ChatWindow messages={messages} onAsk={onAsk} /></div>
}