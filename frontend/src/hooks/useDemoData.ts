import { useEffect, useState } from 'react'
import type { HistoryEntry, Message } from '../types'
import { getApiError } from '../services/api'
import { askQuestion as askQuestionApi, getHistory } from '../services/analysisService'

export const useDemoData = () => {
  const [history, setHistory] = useState<HistoryEntry[]>([])
  const [messages, setMessages] = useState<Message[]>([])
  useEffect(() => { getHistory().then((items) => setHistory(items.map((item) => ({ id: item.id, file: `dataset-${item.dataset_id}`, question: item.question, date: new Date(item.created_at).toLocaleString('fr-FR') })))).catch(() => undefined) }, [])
  const askQuestion = async (question: string, datasetId?: number) => {
    const time = new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
    setMessages((current) => [...current, { id: Date.now(), role: 'user', content: question, timestamp: time }])
    try { if (!datasetId) throw new Error('Importez un fichier avant de poser une question.'); const answer = await askQuestionApi(datasetId, question); setMessages((current) => [...current, { id: Date.now() + 1, role: 'assistant', content: answer.content, timestamp: time }]) } catch (error) { setMessages((current) => [...current, { id: Date.now() + 1, role: 'assistant', content: getApiError(error), timestamp: time }]) }
  }
  return { history, messages, askQuestion }
}