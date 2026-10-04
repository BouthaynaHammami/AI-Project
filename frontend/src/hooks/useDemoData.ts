import { useEffect, useState } from 'react'
import type { ConversationTurn, HistoryEntry, Message } from '../types'
import { getApiError } from '../services/api'
import { askQuestion as askQuestionApi, deleteFeedback as deleteFeedbackApi, getHistory, saveFeedback as saveFeedbackApi } from '../services/analysisService'
import { getDatasetHistory, getDatasetPreview } from '../services/fileService'

export const useDemoData = () => {
  const [history, setHistory] = useState<HistoryEntry[]>([])
  const [messages, setMessages] = useState<Message[]>([])
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [conversationId, setConversationId] = useState<number | null>(null)
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
      generatedCode: null,
      codeExplanation: null,
      codeRetried: false,
      feedback: null,
      conversationId: null,
      conversationTitle: null,
      date: dataset.created_at,
    }))

    const discussionsByKey = new Map<string, typeof analyses>()
    for (const analysis of analyses) {
      const key = analysis.conversation_id === null ? `analysis-${analysis.id}` : `conversation-${analysis.conversation_id}`
      discussionsByKey.set(key, [...(discussionsByKey.get(key) ?? []), analysis])
    }
    const discussions: HistoryEntry[] = Array.from(discussionsByKey.values()).map((items) => {
      items.sort((left, right) => Date.parse(left.created_at) - Date.parse(right.created_at))
      const analysis = items[0]
      const latest = items[items.length - 1]
      let datasetIds = latest.conversation_dataset_ids.length
        ? latest.conversation_dataset_ids
        : [analysis.dataset_id]
      try {
        const resultData = latest.result_data ? JSON.parse(latest.result_data) as { dataset_ids?: unknown } : null
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
      const turns: ConversationTurn[] = items
        .slice()
        .sort((left, right) => Date.parse(left.created_at) - Date.parse(right.created_at))
        .map((item) => ({
          analysisId: item.id,
          question: item.question,
          answer: item.answer,
          chartConfig: item.chart_config,
          generatedCode: item.generated_code,
          codeExplanation: item.code_explanation,
          codeRetried: item.code_retried,
          feedback: item.feedback,
          createdAt: item.created_at,
        }))

      return {
        id: analysis.conversation_id === null ? -analysis.id : -1_000_000_000 - analysis.conversation_id,
        kind: 'discussion',
        file,
        datasetId: latest.dataset_id,
        datasetIds: datasetIds.length ? datasetIds : [analysis.dataset_id],
        question: latest.question,
        answer: latest.answer,
        chartConfig: latest.chart_config,
        generatedCode: latest.generated_code,
        codeExplanation: latest.code_explanation,
        codeRetried: latest.code_retried,
        feedback: latest.feedback,
        conversationId: analysis.conversation_id,
        conversationTitle: latest.conversation_title,
        conversationMessages: turns,
        date: latest.created_at,
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
    const turns = entry.conversationMessages ?? [{
          analysisId: Math.abs(entry.id),
          question: entry.question,
          answer: entry.answer,
          chartConfig: entry.chartConfig,
          generatedCode: entry.generatedCode,
          codeExplanation: entry.codeExplanation,
          codeRetried: entry.codeRetried,
          feedback: entry.feedback,
          createdAt: entry.date,
        }]
    const messagesForEntry: Message[] = entry.kind === 'discussion'
      ? turns.flatMap((turn) => [
          { id: turn.analysisId * 2, role: 'user' as const, content: turn.question, timestamp: new Date(turn.createdAt).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }) },
          { id: turn.analysisId * 2 + 1, analysisId: turn.analysisId, role: 'assistant' as const, content: turn.answer, timestamp: new Date(turn.createdAt).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }), chartConfig: turn.chartConfig, generatedCode: turn.generatedCode, codeExplanation: turn.codeExplanation, codeRetried: turn.codeRetried, feedback: turn.feedback },
        ])
      : []

    setMessages(messagesForEntry)
    setConversationId(entry.conversationId)
    return {
      datasets,
      question: entry.question,
      chartConfig: entry.chartConfig,
      generatedCode: entry.generatedCode,
      codeExplanation: entry.codeExplanation,
      codeRetried: entry.codeRetried,
      conversationId: entry.conversationId,
    }
  }
  const askQuestion = async (question: string, datasetIds?: number[]) => {
    const time = new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
    setMessages((current) => [...current, { id: Date.now(), role: 'user', content: question, timestamp: time }])
      setIsAnalyzing(true)
      try {
        if (!datasetIds || datasetIds.length === 0) throw new Error('Importez un fichier avant de poser une question.')
        const answer = await askQuestionApi(datasetIds, question, conversationId)
        setConversationId(answer.conversation_id)
        setMessages((current) => [...current, {
          id: Date.now() + 1,
          role: 'assistant',
          analysisId: answer.id,
          content: answer.content,
          timestamp: time,
          chartConfig: answer.chart_config,
          generatedCode: answer.generated_code,
          codeExplanation: answer.code_explanation,
          codeRetried: answer.code_retried,
          feedback: answer.feedback,
        }])
        await refreshHistory()
        return answer
      } catch (error) {
        setMessages((current) => [...current, { id: Date.now() + 1, role: 'assistant', content: getApiError(error), timestamp: time }])
        return undefined
      } finally {
        setIsAnalyzing(false)
      }
  }
  const saveFeedback = async (analysisId: number, rating: 1 | -1, comment: string | null) => {
    const feedback = await saveFeedbackApi(analysisId, rating, comment)
    setMessages((current) => current.map((message) => (
      message.analysisId === analysisId ? { ...message, feedback } : message
    )))
    await refreshHistory()
  }
  const clearFeedback = async (analysisId: number) => {
    await deleteFeedbackApi(analysisId)
    setMessages((current) => current.map((message) => (
      message.analysisId === analysisId ? { ...message, feedback: null } : message
    )))
    await refreshHistory()
  }
  const newConversation = () => {
    setConversationId(null)
    setMessages([])
  }
  return { history, messages, isAnalyzing, conversationId, askQuestion, loadHistoryEntry, refreshHistory, saveFeedback, clearFeedback, newConversation }
}