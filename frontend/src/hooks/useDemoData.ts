import { useCallback, useEffect, useState } from 'react'
import type { HistoryEntry, Message } from '../types'
import { getApiError } from '../services/api'
import {
  addConversationMessage,
  createConversation as createConversationApi,
  deleteConversation,
  getConversation,
  getConversations,
  updateConversation,
} from '../services/analysisService'
import { getDatasetPreview } from '../services/fileService'

function parseResultTable(resultData?: string | null): { headers: string[]; rows: string[][] } | undefined {
  if (!resultData) return undefined
  try {
    const result = JSON.parse(resultData) as {
      result_table?: { columns?: unknown; rows?: unknown }
    }
    const table = result.result_table
    if (
      !table
      || !Array.isArray(table.columns)
      || !table.columns.every((column): column is string => typeof column === 'string')
      || !Array.isArray(table.rows)
      || !table.rows.every((row) => Array.isArray(row))
    ) return undefined
    return {
      headers: table.columns,
      rows: table.rows.map((row) => row.map((cell) => cell == null ? '' : String(cell))),
    }
  } catch {
    return undefined
  }
}

export const useDemoData = () => {
  const [history, setHistory] = useState<HistoryEntry[]>([])
  const [messages, setMessages] = useState<Message[]>([])
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [activeConversationId, setActiveConversationId] = useState<number | null>(null)
  const [historyError, setHistoryError] = useState('')
  const refreshHistory = useCallback(async () => {
    try {
      const conversations = await getConversations()
      const entries: HistoryEntry[] = conversations.map((conversation) => {
        const datasetIds = conversation.dataset_ids
        return {
          id: conversation.id,
          kind: 'discussion',
          file: 'Discussion',
          datasetId: datasetIds[0] ?? 0,
          datasetIds,
          question: conversation.title,
          answer: '',
          chartConfig: null,
          generatedCode: null,
          codeExplanation: null,
          codeRetried: false,
          feedback: null,
          conversationId: conversation.id,
          conversationTitle: conversation.title,
          date: conversation.updated_at,
          analysisId: null,
          title: conversation.title,
          isFavorite: conversation.is_favorite,
        }
      })
      setHistory(entries)
      setHistoryError('')
    } catch (error) {
      setHistoryError(getApiError(error))
      throw error
    }
  }, [])

  useEffect(() => {
    void refreshHistory().catch(() => undefined)
  }, [refreshHistory])

  const createNewConversation = async (datasetIds: number[] = []) => {
    try {
      const conversation = await createConversationApi(datasetIds)
      setActiveConversationId(conversation.id)
      setMessages([])
      await refreshHistory()
      return conversation.id
    } catch (error) {
      setHistoryError(getApiError(error))
      throw error
    }
  }

  const updateConversationDatasets = async (conversationId: number, datasetIds: number[]) => {
    try {
      await updateConversation(conversationId, { dataset_ids: datasetIds })
      await refreshHistory()
    } catch (error) {
      setHistoryError(getApiError(error))
      throw error
    }
  }

  const loadHistoryEntry = async (id: number) => {
    try {
      const conversation = await getConversation(id)
      const datasets = await Promise.all(conversation.dataset_ids.map(getDatasetPreview))
      const loadedMessages: Message[] = conversation.messages.map((message) => {
        const result = message.result_data
        return {
          id: message.id,
          role: message.role,
          content: message.content,
          timestamp: new Date(message.created_at).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }),
          chartConfig: result?.chart_config ?? null,
          resultData: result?.result_data ?? null,
          resultTable: parseResultTable(result?.result_data),
        }
      })
      setMessages(loadedMessages)
      setActiveConversationId(conversation.id)
      const firstQuestion = loadedMessages.find((message) => message.role === 'user')?.content ?? conversation.title
      const lastChartConfig = [...loadedMessages].reverse().find((message) => message.role === 'assistant')?.chartConfig ?? null
      setHistoryError('')
      return { datasets, question: firstQuestion, chartConfig: lastChartConfig }
    } catch (error) {
      setHistoryError(getApiError(error))
      throw error
    }
  }

  const askQuestion = async (question: string, datasetIds: number[], conversationId: number) => {
    const time = new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
    setMessages((current) => [...current, { id: Date.now(), role: 'user', content: question, timestamp: time }])
    setIsAnalyzing(true)
    try {
      if (!datasetIds.length) throw new Error('Importez un fichier avant de poser une question.')
      const answer = await addConversationMessage(conversationId, datasetIds, question)
      setMessages((current) => [
        ...current,
        {
          id: answer.id,
          role: 'assistant',
          content: answer.content,
          timestamp: new Date(answer.created_at).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }),
          chartConfig: answer.chart_config,
          resultData: answer.result_data,
          resultTable: parseResultTable(answer.result_data),
        },
      ])
      void refreshHistory().catch(() => undefined)
      return answer
    } catch (error) {
      setMessages((current) => [...current, { id: Date.now() + 1, role: 'assistant', content: getApiError(error), timestamp: time }])
      return undefined
    } finally {
      setIsAnalyzing(false)
    }
  }

  const remove = async (entry: HistoryEntry) => {
    if (entry.conversationId === null) return
    try {
      await deleteConversation(entry.conversationId)
      if (activeConversationId === entry.conversationId) {
        setActiveConversationId(null)
        setMessages([])
      }
      await refreshHistory()
    } catch (error) {
      setHistoryError(getApiError(error))
    }
  }

  const rename = async (entry: HistoryEntry, title: string) => {
    if (entry.conversationId === null) return
    try {
      await updateConversation(entry.conversationId, { title })
      await refreshHistory()
    } catch (error) {
      setHistoryError(getApiError(error))
    }
  }

  const toggleFavorite = async (entry: HistoryEntry) => {
    if (entry.conversationId === null) return
    try {
      await updateConversation(entry.conversationId, { is_favorite: !entry.isFavorite })
      await refreshHistory()
    } catch (error) {
      setHistoryError(getApiError(error))
    }
  }

  return {
    history,
    messages,
    isAnalyzing,
    activeConversationId,
    historyError,
    askQuestion,
    createNewConversation,
    updateConversationDatasets,
    loadHistoryEntry,
    refreshHistory,
    remove,
    rename,
    toggleFavorite,
  }
}
