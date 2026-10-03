import { useEffect, useState } from 'react'
import type { HistoryEntry, Message } from '../types'
import { getApiError } from '../services/api'
import { askQuestion as askQuestionApi, getHistory } from '../services/analysisService'
import { getDatasetHistory, getDatasetPreview } from '../services/fileService'

export const useDemoData = () => {
  const [history, setHistory] = useState<HistoryEntry[]>([])
  const [messages, setMessages] = useState<Message[]>([])
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const refreshHistory = async () => {
    const [datasets, analyses] = await Promise.all([getDatasetHistory(), getHistory()])
    const imports: HistoryEntry[] = datasets.map((dataset) => ({
      id: dataset.id,
      kind: 'import',
      file: dataset.filename,
      datasetId: dataset.id,
      datasetIds: [dataset.id],
      question: '',
      answer: '',
      chartConfig: null,
      date: dataset.created_at,
    }))

    const discussions: HistoryEntry[] = analyses.map((analysis) => {
      let datasetIds = [analysis.dataset_id]
      try {
        const resultData = analysis.result_data ? JSON.parse(analysis.result_data) as { dataset_ids?: unknown } : null
        if (Array.isArray(resultData?.dataset_ids)) {
          datasetIds = resultData.dataset_ids.filter((id): id is number => Number.isInteger(id))
        }
      } catch {
        datasetIds = [analysis.dataset_id]
      }

      const file = datasetIds
        .map((id) => datasets.find((dataset) => dataset.id === id)?.filename)
        .filter((filename): filename is string => Boolean(filename))
        .join(', ') || 'Discussion'

      return {
        id: -analysis.id,
        kind: 'discussion',
        file,
        datasetId: analysis.dataset_id,
        datasetIds: datasetIds.length ? datasetIds : [analysis.dataset_id],
        question: analysis.question,
        answer: analysis.answer,
        chartConfig: analysis.chart_config,
        date: analysis.created_at,
      }
    })

    setHistory([...imports, ...discussions].sort((left, right) => Date.parse(right.date) - Date.parse(left.date)).map((entry) => ({
      ...entry,
      date: new Date(entry.date).toLocaleString('fr-FR'),
    })))
  }
  useEffect(() => { refreshHistory().catch(() => undefined) }, [])
  const loadHistoryEntry = async (id: number) => {
    const entry = history.find((item) => item.id === id)
    if (!entry) return null

    const datasets = await Promise.all(entry.datasetIds.map(getDatasetPreview))
    const messagesForEntry: Message[] = entry.kind === 'discussion'
      ? [
          { id: Math.abs(entry.id) * 2, role: 'user', content: entry.question, timestamp: new Date(entry.date).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }) },
          { id: Math.abs(entry.id) * 2 + 1, role: 'assistant', content: entry.answer, timestamp: new Date(entry.date).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }), chartConfig: entry.chartConfig },
        ]
      : []

    setMessages(messagesForEntry)
    return {
      datasets,
      question: entry.question,
      chartConfig: entry.chartConfig,
    }
  }
    const askQuestion = async (question: string, datasetIds?: number[]) => {
    const time = new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
    setMessages((current) => [...current, { id: Date.now(), role: 'user', content: question, timestamp: time }])
      setIsAnalyzing(true)
      try {
        if (!datasetIds || datasetIds.length === 0) throw new Error('Importez un fichier avant de poser une question.')
        const answer = await askQuestionApi(datasetIds, question)
        setMessages((current) => [...current, { id: Date.now() + 1, role: 'assistant', content: answer.content, timestamp: time, chartConfig: answer.chart_config }])
        await refreshHistory()
        return answer
      } catch (error) {
        setMessages((current) => [...current, { id: Date.now() + 1, role: 'assistant', content: getApiError(error), timestamp: time }])
        return undefined
      } finally {
        setIsAnalyzing(false)
      }
  }
    return { history, messages, isAnalyzing, askQuestion, loadHistoryEntry, refreshHistory }
}