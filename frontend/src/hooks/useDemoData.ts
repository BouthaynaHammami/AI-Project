import { useCallback, useEffect, useRef, useState } from 'react'
import type { ConversationTurn, HistoryEntry, Message } from '../types'
import { getApiError } from '../services/api'
import {
  askQuestion as askQuestionApi,
  deleteAnalysis,
  deleteFeedback as deleteFeedbackApi,
  getHistory,
  restoreAnalysis,
  saveFeedback as saveFeedbackApi,
  updateAnalysis,
  type AnalysisHistory,
} from '../services/analysisService'
import { deleteDataset, getDatasetHistory, getDatasetPreview, type DatasetHistory } from '../services/fileService'

type CascadePrompt = { entry: HistoryEntry; count: number }
type PendingDelete = { entry: HistoryEntry; timer: number }

function buildHistory(datasets: DatasetHistory[], analyses: AnalysisHistory[]): HistoryEntry[] {
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

  const discussionsByKey = new Map<string, AnalysisHistory[]>()
  for (const analysis of analyses) {
    const key = analysis.conversation_id === null ? `analysis-${analysis.id}` : `conversation-${analysis.conversation_id}`
    discussionsByKey.set(key, [...(discussionsByKey.get(key) ?? []), analysis])
  }
  const discussions: HistoryEntry[] = Array.from(discussionsByKey.values()).map((items) => {
    items.sort((left, right) => Date.parse(left.created_at) - Date.parse(right.created_at))
    const first = items[0]
    const latest = items[items.length - 1]
    let datasetIds = latest.conversation_dataset_ids.length
      ? latest.conversation_dataset_ids
      : latest.dataset_id === null ? [] : [latest.dataset_id]
    try {
      const resultData = latest.result_data ? JSON.parse(latest.result_data) as { dataset_ids?: unknown } : null
      if (Array.isArray(resultData?.dataset_ids)) {
        datasetIds = resultData.dataset_ids.filter((id): id is number => Number.isInteger(id))
      }
    } catch {
      datasetIds = latest.dataset_id === null ? [] : [latest.dataset_id]
    }

    const file = datasetIds
      .map((id) => datasets.find((dataset) => dataset.id === id)?.filename)
      .filter((filename): filename is string => Boolean(filename))
      .join(', ') || 'Discussion'
    const turns: ConversationTurn[] = items.map((item) => ({
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
      id: first.conversation_id === null ? -first.id : -1_000_000_000 - first.conversation_id,
      kind: 'discussion',
      file,
      datasetId: latest.dataset_id ?? datasetIds[0] ?? 0,
      datasetIds,
      question: latest.question,
      answer: latest.answer,
      chartConfig: latest.chart_config,
      generatedCode: latest.generated_code,
      codeExplanation: latest.code_explanation,
      codeRetried: latest.code_retried,
      feedback: latest.feedback,
      conversationId: first.conversation_id,
      conversationTitle: latest.conversation_title,
      conversationMessages: turns,
      date: latest.created_at,
      analysisId: latest.id,
      title: latest.title || latest.conversation_title || latest.question,
      isFavorite: latest.is_favorite,
    }
  })
  return [...imports, ...discussions].sort((left, right) => Date.parse(right.date) - Date.parse(left.date))
}

export const useDemoData = () => {
  const [history, setHistory] = useState<HistoryEntry[]>([])
  const [datasetRecords, setDatasetRecords] = useState<DatasetHistory[]>([])
  const [analysisRecords, setAnalysisRecords] = useState<AnalysisHistory[]>([])
  const [messages, setMessages] = useState<Message[]>([])
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [conversationId, setConversationId] = useState<number | null>(null)
  const [query, setQuery] = useState('')
  const [favoriteOnly, setFavoriteOnly] = useState(false)
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [hasMore, setHasMore] = useState(false)
  const [historyError, setHistoryError] = useState('')
  const [undoEntry, setUndoEntry] = useState<HistoryEntry | null>(null)
  const [cascadePrompt, setCascadePrompt] = useState<CascadePrompt | null>(null)
  const requestRef = useRef<AbortController | null>(null)
  const pendingDeleteRef = useRef<PendingDelete | null>(null)

  const fetchHistory = useCallback(async (
    searchText: string,
    onlyFavorites: boolean,
    append: boolean,
  ) => {
    if (!append) {
      requestRef.current?.abort()
      requestRef.current = new AbortController()
    }
    const signal = requestRef.current?.signal
    const offset = append ? analysisRecords.length : 0
    setLoadingHistory(true)
    setHistoryError('')
    try {
      const [datasets, page] = await Promise.all([
        getDatasetHistory(),
        getHistory(
          { q: searchText || undefined, favorite: onlyFavorites || undefined, limit: 20, offset },
          signal,
        ),
      ])
      if (signal?.aborted) return
      const nextAnalyses = append ? [...analysisRecords, ...page.items] : page.items
      setDatasetRecords(datasets)
      setAnalysisRecords(nextAnalyses)
      const lowerQuery = searchText.trim().toLocaleLowerCase()
      const visibleDatasets = onlyFavorites
        ? []
        : datasets.filter((dataset) => !lowerQuery || dataset.filename.toLocaleLowerCase().includes(lowerQuery))
      setHistory(buildHistory(visibleDatasets, nextAnalyses))
      setHasMore(page.has_more)
    } catch (error) {
      if (!signal?.aborted) setHistoryError(getApiError(error))
    } finally {
      if (!signal?.aborted) setLoadingHistory(false)
    }
  }, [analysisRecords])

  const refreshHistory = useCallback(
    () => fetchHistory(query, favoriteOnly, false),
    [fetchHistory, favoriteOnly, query],
  )

  useEffect(() => {
    void refreshHistory()
    return () => requestRef.current?.abort()
  }, [])

  const search = useCallback(async (nextQuery: string, nextFavoriteOnly = favoriteOnly) => {
    setQuery(nextQuery)
    setFavoriteOnly(nextFavoriteOnly)
    await fetchHistory(nextQuery, nextFavoriteOnly, false)
  }, [favoriteOnly, fetchHistory])

  const loadMore = useCallback(
    () => fetchHistory(query, favoriteOnly, true),
    [fetchHistory, favoriteOnly, query],
  )

  const loadHistoryEntry = async (id: number) => {
    const entry = history.find((item) => item.id === id)
    if (!entry) return null
    const existingIds = new Set(datasetRecords.map((dataset) => dataset.id))
    const datasets = await Promise.all(
      entry.datasetIds.filter((datasetId) => existingIds.has(datasetId)).map(getDatasetPreview),
    )
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

  const rename = async (entry: HistoryEntry, title: string) => {
    if (!entry.analysisId) return
    const previous = history
    const normalizedTitle = title.trim()
    setHistory((items) => items.map((item) => item.id === entry.id ? { ...item, title: normalizedTitle || item.question } : item))
    try {
      const updated = await updateAnalysis(entry.analysisId, { title: normalizedTitle || null })
      setAnalysisRecords((items) => items.map((item) => item.id === updated.id ? updated : item))
      await refreshHistory()
    } catch (error) {
      setHistory(previous)
      throw error
    }
  }

  const toggleFavorite = async (entry: HistoryEntry) => {
    if (!entry.analysisId) return
    const previous = history
    const nextValue = !entry.isFavorite
    setHistory((items) => items.map((item) => item.id === entry.id ? { ...item, isFavorite: nextValue } : item))
    try {
      await updateAnalysis(entry.analysisId, { is_favorite: nextValue })
      if (favoriteOnly && !nextValue) setHistory((items) => items.filter((item) => item.id !== entry.id))
      await refreshHistory()
    } catch (error) {
      setHistory(previous)
      throw error
    }
  }

  const restoreInList = (entry: HistoryEntry) => {
    setHistory((items) => [...items, entry].sort((left, right) => Date.parse(right.date) - Date.parse(left.date)))
  }

  const remove = async (entry: HistoryEntry) => {
    setHistory((items) => items.filter((item) => item.id !== entry.id))
    setUndoEntry(entry)
    try {
      if (entry.kind === 'discussion' && entry.analysisId) await deleteAnalysis(entry.analysisId)
      const timer = window.setTimeout(() => {
        if (entry.kind === 'import') {
          void deleteDataset(entry.datasetId, false).then(() => {
            if (pendingDeleteRef.current?.entry.id === entry.id) pendingDeleteRef.current = null
            setUndoEntry((current) => current?.id === entry.id ? null : current)
            void refreshHistory()
          }).catch((error: unknown) => {
            const data = (error as { response?: { status?: number; data?: { detail?: { analysis_count?: number } } } })?.response
            if (data?.status === 409) {
              setCascadePrompt({ entry, count: data.data?.detail?.analysis_count ?? 0 })
              return
            }
            restoreInList(entry)
            setUndoEntry((current) => current?.id === entry.id ? null : current)
            setHistoryError(getApiError(error))
          })
        } else {
          if (pendingDeleteRef.current?.entry.id === entry.id) pendingDeleteRef.current = null
          setUndoEntry((current) => current?.id === entry.id ? null : current)
        }
      }, 5000)
      pendingDeleteRef.current = { entry, timer }
    } catch (error) {
      restoreInList(entry)
      setUndoEntry((current) => current?.id === entry.id ? null : current)
      setHistoryError(getApiError(error))
    }
  }

  const undoRemove = async () => {
    const pending = pendingDeleteRef.current
    const entry = undoEntry ?? pending?.entry
    if (!entry) return
    if (pending) window.clearTimeout(pending.timer)
    pendingDeleteRef.current = null
    try {
      if (entry.kind === 'discussion' && entry.analysisId) await restoreAnalysis(entry.analysisId)
      restoreInList(entry)
      setUndoEntry(null)
      await refreshHistory()
    } catch (error) {
      setHistoryError(getApiError(error))
      setUndoEntry(null)
    }
  }

  const confirmCascadeDelete = async () => {
    if (!cascadePrompt) return
    try {
      await deleteDataset(cascadePrompt.entry.datasetId, true)
      setCascadePrompt(null)
      setUndoEntry(null)
      pendingDeleteRef.current = null
      await refreshHistory()
    } catch (error) {
      restoreInList(cascadePrompt.entry)
      setHistoryError(getApiError(error))
      setCascadePrompt(null)
    }
  }

  const cancelCascadeDelete = () => {
    if (cascadePrompt) restoreInList(cascadePrompt.entry)
    setCascadePrompt(null)
    setUndoEntry(null)
    pendingDeleteRef.current = null
  }

  const newConversation = () => {
    setConversationId(null)
    setMessages([])
  }

  return {
    history,
    messages,
    isAnalyzing,
    conversationId,
    query,
    favoriteOnly,
    loadingHistory,
    hasMore,
    historyError,
    undoEntry,
    cascadePrompt,
    askQuestion,
    loadHistoryEntry,
    refreshHistory,
    search,
    loadMore,
    rename,
    toggleFavorite,
    remove,
    undoRemove,
    confirmCascadeDelete,
    cancelCascadeDelete,
    saveFeedback,
    clearFeedback,
    newConversation,
  }
}
