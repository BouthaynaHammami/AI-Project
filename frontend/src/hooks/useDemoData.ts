import { useCallback, useEffect, useRef, useState } from 'react'
import type { HistoryEntry, Message } from '../types'
import { getApiError } from '../services/api'
import {
  addConversationMessage,
  createConversation as createConversationApi,
  deleteConversation,
  deleteAnalysis,
  getConversation,
  getConversations,
  restoreAnalysis,
  updateConversation,
} from '../services/analysisService'
import type { ConversationSummary } from '../services/analysisService'
import { deleteDataset, getDatasetHistory, getDatasetPreview } from '../services/fileService'

type PendingRemoval = { entry: HistoryEntry; analysisId: number | null; timer: number }

function toHistoryEntry(conversation: ConversationSummary): HistoryEntry {
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
}

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
  const [historyLoading, setHistoryLoading] = useState(false)
  const [hasMoreHistory, setHasMoreHistory] = useState(false)
  const [undoEntry, setUndoEntry] = useState<HistoryEntry | null>(null)
  const [cascadePrompt, setCascadePrompt] = useState<{ item: HistoryEntry; analysisCount: number } | null>(null)
  const pendingRemoval = useRef<PendingRemoval | null>(null)
  const searchOptions = useRef<{ q?: string; favorite?: boolean }>({})
  const nextOffset = useRef(0)
  const historyRequest = useRef<AbortController | null>(null)
  const refreshHistory = useCallback(async (options = searchOptions.current) => {
    historyRequest.current?.abort()
    const controller = new AbortController()
    historyRequest.current = controller
    searchOptions.current = options
    setHistoryLoading(true)
    try {
      const [conversations, datasets] = await Promise.all([
        getConversations({ ...options, limit: 20, offset: 0, signal: controller.signal }),
        getDatasetHistory(),
      ])
      if (controller.signal.aborted) return
      const entries = conversations.map(toHistoryEntry)
      nextOffset.current = conversations.length
      setHasMoreHistory(conversations.length === 20)
      const imports: HistoryEntry[] = datasets
        .filter((dataset) => {
          const term = options.q?.trim().toLocaleLowerCase()
          return !options.favorite && (!term || dataset.filename.toLocaleLowerCase().includes(term))
        })
        .map((dataset) => ({
        id: dataset.id,
        kind: 'import',
        file: dataset.filename,
        datasetId: dataset.id,
        datasetIds: [dataset.id],
        question: dataset.filename,
        answer: '',
        chartConfig: null,
        generatedCode: null,
        codeExplanation: null,
        codeRetried: false,
        feedback: null,
        conversationId: null,
        conversationTitle: null,
        date: dataset.created_at,
        analysisId: null,
        title: dataset.filename,
        isFavorite: false,
        }))
      setHistory([...entries, ...imports].sort((left, right) => Date.parse(right.date) - Date.parse(left.date)))
      setHistoryError('')
    } catch (error) {
      if (controller.signal.aborted) return
      setHistoryError(getApiError(error))
      throw error
    } finally {
      if (historyRequest.current === controller) setHistoryLoading(false)
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
          analysisId: message.analysis_id ?? undefined,
          role: message.role,
          content: message.content,
          timestamp: new Date(message.created_at).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }),
          chartConfig: result?.chart_config ?? null,
          resultData: result?.result_data ?? null,
          resultTable: parseResultTable(result?.result_data),
          generatedCode: result?.generated_code ?? null,
          codeExplanation: result?.code_explanation ?? null,
          codeRetried: result?.code_retried ?? false,
          feedback: result?.feedback ?? null,
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

  const selectDataset = () => {
    setActiveConversationId(null)
    setMessages([])
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
          analysisId: answer.id,
          role: 'assistant',
          content: answer.content,
          timestamp: new Date(answer.created_at).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }),
          chartConfig: answer.chart_config,
          resultData: answer.result_data,
          resultTable: parseResultTable(answer.result_data),
          generatedCode: answer.generated_code ?? null,
          codeExplanation: answer.code_explanation ?? null,
          codeRetried: answer.code_retried ?? false,
          feedback: answer.feedback ?? null,
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

  const clearPendingRemoval = () => {
    if (pendingRemoval.current) window.clearTimeout(pendingRemoval.current.timer)
    pendingRemoval.current = null
  }

  const finalizePendingRemoval = async () => {
    const pending = pendingRemoval.current
    if (!pending) return true
    clearPendingRemoval()
    setUndoEntry(null)
    if (pending.analysisId !== null) return true
    try {
      if (pending.entry.kind === 'import') {
        await deleteDataset(pending.entry.datasetId)
      } else if (pending.entry.conversationId !== null) {
        await deleteConversation(pending.entry.conversationId)
      }
      return true
    } catch (error) {
      const response = typeof error === 'object' && error !== null && 'response' in error
        ? (error as { response?: { status?: number; data?: { analysis_count?: number } } }).response
        : undefined
      if (pending.entry.kind === 'import' && response?.status === 409) {
        setCascadePrompt({ item: pending.entry, analysisCount: response.data?.analysis_count ?? 0 })
      } else {
        setHistoryError(getApiError(error))
        setHistory((current) => [...current, pending.entry])
      }
      return false
    }
  }

  const remove = async (entry: HistoryEntry) => {
    if (!(await finalizePendingRemoval())) return
    setCascadePrompt(null)
    setUndoEntry(entry)
    setHistory((current) => current.filter((item) => !(item.id === entry.id && item.kind === entry.kind)))
    if (entry.kind === 'import') {
      const timer = window.setTimeout(() => {
        void deleteDataset(entry.datasetId).then(() => {
          pendingRemoval.current = null
          setUndoEntry(null)
        }).catch((error: unknown) => {
          const response = typeof error === 'object' && error !== null && 'response' in error
            ? (error as { response?: { status?: number; data?: { analysis_count?: number } } }).response
            : undefined
          if (response?.status === 409) {
            setCascadePrompt({ item: entry, analysisCount: response.data?.analysis_count ?? 0 })
            setUndoEntry(null)
          } else {
            setHistoryError(getApiError(error))
            setHistory((current) => [...current, entry])
            setUndoEntry(null)
          }
          pendingRemoval.current = null
        })
      }, 5000)
      pendingRemoval.current = { entry, analysisId: null, timer }
      return
    }
    if (entry.conversationId === null) return
    try {
      const conversation = await getConversation(entry.conversationId)
      const analysisId = conversation.messages.find((message) => message.role === 'assistant' && message.analysis_id)?.analysis_id ?? null
      if (analysisId !== null) {
        await deleteAnalysis(analysisId)
      } else {
        const timer = window.setTimeout(() => {
          void deleteConversation(entry.conversationId!).then(() => {
            pendingRemoval.current = null
            setUndoEntry(null)
          }).catch((error: unknown) => {
            setHistoryError(getApiError(error))
            pendingRemoval.current = null
            setUndoEntry(null)
          })
        }, 5000)
        pendingRemoval.current = { entry, analysisId: null, timer }
      }
      if (activeConversationId === entry.conversationId) {
        setActiveConversationId(null)
        setMessages([])
      }
      if (analysisId !== null) {
        const timer = window.setTimeout(() => {
          pendingRemoval.current = null
          setUndoEntry(null)
        }, 5000)
        pendingRemoval.current = { entry, analysisId, timer }
      }
    } catch (error) {
      setHistoryError(getApiError(error))
      setHistory((current) => [...current, entry])
      setUndoEntry(null)
    }
  }

  const undoRemove = async () => {
    const pending = pendingRemoval.current
    if (!pending) return
    clearPendingRemoval()
    setUndoEntry(null)
    setCascadePrompt(null)
    if (pending.analysisId !== null) {
      try {
        await restoreAnalysis(pending.analysisId)
        await refreshHistory()
      } catch (error) {
        setHistoryError(getApiError(error))
      }
    } else if (pending.entry.kind === 'import') {
      setHistory((current) => [...current, pending.entry])
    } else {
      setHistory((current) => [...current, pending.entry])
    }
  }

  const confirmCascade = async () => {
    if (!cascadePrompt) return
    try {
      await deleteDataset(cascadePrompt.item.datasetId, true)
      setCascadePrompt(null)
      setUndoEntry(null)
      await refreshHistory()
    } catch (error) {
      setHistoryError(getApiError(error))
    }
  }

  const cancelCascade = () => {
    if (cascadePrompt) setHistory((current) => [...current, cascadePrompt.item])
    setCascadePrompt(null)
    setUndoEntry(null)
  }

  const rename = async (entry: HistoryEntry, title: string) => {
    if (entry.conversationId === null) return
    const previous = history
    setHistory((current) => current.map((item) => item.kind === 'discussion' && item.id === entry.id
      ? { ...item, title, question: title, conversationTitle: title }
      : item))
    try {
      await updateConversation(entry.conversationId, { title })
      await refreshHistory()
    } catch (error) {
      setHistory(previous)
      setHistoryError(getApiError(error))
    }
  }

  const toggleFavorite = async (entry: HistoryEntry) => {
    if (entry.conversationId === null) return
    const previous = history
    setHistory((current) => current.map((item) => item.kind === 'discussion' && item.id === entry.id
      ? { ...item, isFavorite: !item.isFavorite }
      : item))
    try {
      await updateConversation(entry.conversationId, { is_favorite: !entry.isFavorite })
      await refreshHistory()
    } catch (error) {
      setHistory(previous)
      setHistoryError(getApiError(error))
    }
  }

  const searchHistory = (query: string, favorite: boolean) => {
    void refreshHistory({ q: query || undefined, favorite: favorite || undefined }).catch(() => undefined)
  }
  const loadMore = async () => {
    if (!hasMoreHistory || historyLoading) return
    const controller = new AbortController()
    historyRequest.current?.abort()
    historyRequest.current = controller
    setHistoryLoading(true)
    try {
      const conversations = await getConversations({
        ...searchOptions.current,
        limit: 20,
        offset: nextOffset.current,
        signal: controller.signal,
      })
      if (controller.signal.aborted) return
      nextOffset.current += conversations.length
      setHasMoreHistory(conversations.length === 20)
      setHistory((current) => [...current, ...conversations.map(toHistoryEntry)]
        .sort((left, right) => Date.parse(right.date) - Date.parse(left.date)))
    } catch (error) {
      if (!controller.signal.aborted) setHistoryError(getApiError(error))
    } finally {
      if (historyRequest.current === controller) setHistoryLoading(false)
    }
  }

  return {
    history,
    hasMore: hasMoreHistory,
    loading: historyLoading,
    messages,
    isAnalyzing,
    activeConversationId,
    historyError,
    askQuestion,
    createNewConversation,
    updateConversationDatasets,
    loadHistoryEntry,
    selectDataset,
    refreshHistory,
    remove,
    rename,
    toggleFavorite,
    undoEntry,
    cascadePrompt,
    undoRemove,
    confirmCascade,
    cancelCascade,
    searchHistory,
    loadMore,
  }
}
