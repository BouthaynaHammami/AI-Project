import { useEffect, useState } from 'react'
import type { HistoryEntry, Message } from '../types'
import { getApiError } from '../services/api'
import { askQuestion as askQuestionApi, getHistory } from '../services/analysisService'
import { getDatasetHistory, getDatasetPreview } from '../services/fileService'

export const useDemoData = () => {
  const [history, setHistory] = useState<HistoryEntry[]>([])
  const [messages, setMessages] = useState<Message[]>([])
  const refreshHistory = async () => {
    const [datasets, analyses] = await Promise.all([getDatasetHistory(), getHistory()])
    setHistory(datasets.map((dataset) => {
      const datasetAnalyses = analyses.filter((item) => item.dataset_id === dataset.id).reverse()
      const latest = datasetAnalyses[datasetAnalyses.length - 1]
      return {
        id: dataset.id,
        file: dataset.filename,
        datasetId: dataset.id,
        question: latest?.question ?? 'Nouvelle analyse',
        answer: latest?.answer ?? '',
        chartConfig: latest?.chart_config ?? null,
        date: new Date(dataset.created_at).toLocaleString('fr-FR'),
        analyses: datasetAnalyses.map((item) => ({ id: item.id, question: item.question, answer: item.answer, chartConfig: item.chart_config, createdAt: item.created_at })),
      }
    }))
  }
  useEffect(() => { refreshHistory().catch(() => undefined) }, [])
  const loadHistoryEntry = async (id: number) => {
    const entry = history.find((item) => item.id === id)
    if (!entry) return null
    const dataset = await getDatasetPreview(entry.datasetId)
    const messages = entry.analyses.flatMap((analysis) => { const timestamp = new Date(analysis.createdAt).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }); return [{ id: analysis.id * 2, role: 'user' as const, content: analysis.question, timestamp }, { id: analysis.id * 2 + 1, role: 'assistant' as const, content: analysis.answer, timestamp }] })
    setMessages(messages)
    return { dataset, question: entry.question, chartConfig: entry.chartConfig }
  }
  const askQuestion = async (question: string, datasetId?: number) => {
    const time = new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
    setMessages((current) => [...current, { id: Date.now(), role: 'user', content: question, timestamp: time }])
    try { if (!datasetId) throw new Error('Importez un fichier avant de poser une question.'); const answer = await askQuestionApi(datasetId, question); setMessages((current) => [...current, { id: Date.now() + 1, role: 'assistant', content: answer.content, timestamp: time }]); await refreshHistory(); return answer } catch (error) { setMessages((current) => [...current, { id: Date.now() + 1, role: 'assistant', content: getApiError(error), timestamp: time }]); return undefined }
  }
  return { history, messages, askQuestion, loadHistoryEntry, refreshHistory }
}