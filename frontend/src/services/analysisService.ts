import { api } from './api'

export type Feedback = { id?: number; rating: -1 | 1; comment: string | null }
export type AnalysisAnswer = {
  id: number
  conversation_id?: number
  dataset_id: number
  question: string
  type: 'text'
  content: string
  result_data?: string | null
  chart_config: string | null
  generated_code?: string | null
  code_explanation?: string | null
  code_retried?: boolean
  feedback?: Feedback | null
  created_at: string
}
export type ConversationSummary = {
  id: number
  title: string
  dataset_ids: number[]
  is_favorite: boolean
  created_at: string
  updated_at: string
}
export type ConversationMessage = {
  id: number
  analysis_id?: number | null
  role: 'user' | 'assistant'
  content: string
  result_data?: {
    chart_config?: string | null
    result_data?: string | null
    generated_code?: string | null
    code_explanation?: string | null
    code_retried?: boolean
    feedback?: Feedback | null
  } | null
  created_at: string
}
export type ConversationDetail = ConversationSummary & { messages: ConversationMessage[] }
export type AnalysisHistory = {
  id: number
  conversation_id?: number | null
  conversation_title?: string | null
  conversation_dataset_ids?: number[]
  dataset_id: number | null
  question: string
  answer: string
  result_type: string
  result_data: string | null
  chart_config: string | null
  generated_code?: string | null
  code_explanation?: string | null
  code_retried?: boolean
  feedback?: Feedback | null
  title?: string | null
  is_favorite?: boolean
  created_at: string
}
export type AnalysisHistoryPage = { items: AnalysisHistory[]; total: number; has_more: boolean }
export type SuggestedQuestion = {
  question: string
  category: 'classement' | 'evolution' | 'comparaison' | 'repartition' | 'qualite' | 'synthese'
  chart: boolean
}
export type ShareLinkSummary = { id: number; expires_at: string; view_count: number }
export type ShareLinkCreated = { id: number; token: string; expires_at: string }
export type PublicSharedAnalysis = {
  question: string
  answer: string
  chart_config: string | null
  created_at: string
}

export async function askQuestion(datasetIds: number[], question: string) {
  const { data } = await api.post<AnalysisAnswer>('/analysis/ask', { dataset_ids: datasetIds, question })
  return data
}

export async function getConversations(params: {
  q?: string
  favorite?: boolean
  limit?: number
  offset?: number
  signal?: AbortSignal
} = {}) {
  const { signal, ...query } = params
  const { data } = await api.get<ConversationSummary[]>('/conversations', { params: query, signal })
  return data
}

export async function createConversation(datasetIds: number[] = []) {
  const { data } = await api.post<ConversationSummary>('/conversations', { dataset_ids: datasetIds })
  return data
}

export async function getConversation(conversationId: number) {
  const { data } = await api.get<ConversationDetail>(`/conversations/${conversationId}`)
  return data
}

export async function addConversationMessage(conversationId: number, datasetIds: number[], question: string) {
  const { data } = await api.post<AnalysisAnswer>(`/conversations/${conversationId}/messages`, {
    dataset_ids: datasetIds,
    question,
  })
  return data
}

export async function updateConversation(
  conversationId: number,
  update: { title?: string; is_favorite?: boolean; dataset_ids?: number[] },
) {
  const { data } = await api.patch<ConversationSummary>(`/conversations/${conversationId}`, update)
  return data
}

export async function deleteConversation(conversationId: number) {
  await api.delete(`/conversations/${conversationId}`)
}

export async function getHistory(params: { q?: string; favorite?: boolean; limit?: number; offset?: number } = {}) {
  const { data } = await api.get<AnalysisHistoryPage>('/analysis/history', { params })
  return data
}

export async function updateAnalysis(analysisId: number, update: { title?: string | null; is_favorite?: boolean }) {
  const { data } = await api.patch<AnalysisHistory>(`/analysis/${analysisId}`, update)
  return data
}

export async function deleteAnalysis(analysisId: number) {
  await api.delete(`/analysis/${analysisId}`)
}

export async function exportAnalysis(analysisId: number, format: 'pdf' | 'xlsx') {
  const response = await api.get<Blob>(`/analysis/${analysisId}/export`, {
    params: { format },
    responseType: 'blob',
  })
  const disposition = response.headers['content-disposition'] as string | undefined
  const filenameMatch = disposition?.match(/filename=(?:"([^"]+)"|([^;]+))/i)
  const filename = filenameMatch?.[1] ?? filenameMatch?.[2]?.trim()
  return {
    blob: response.data,
    filename: filename && !/[\\/\r\n]/.test(filename) ? filename : `analyse-${analysisId}.${format}`,
  }
}

export async function restoreAnalysis(analysisId: number) {
  const { data } = await api.post<AnalysisHistory>(`/analysis/${analysisId}/restore`)
  return data
}

export async function saveFeedback(analysisId: number, feedback: Omit<Feedback, 'id'>) {
  const { data } = await api.put<Feedback>(`/analysis/${analysisId}/feedback`, feedback)
  return data
}

export async function deleteFeedback(analysisId: number) {
  await api.delete(`/analysis/${analysisId}/feedback`)
}

export async function getSuggestions(datasetIds: number[], refresh = false, signal?: AbortSignal) {
  const { data } = await api.get<{ suggestions: SuggestedQuestion[]; source: 'ai' | 'rules' | 'cache' }>(
    '/analysis/suggestions',
    {
      params: { dataset_ids: datasetIds.join(','), refresh },
      signal,
    },
  )
  return data
}

export async function createShareLink(analysisId: number, expiresInDays: 1 | 7 | 30) {
  const { data } = await api.post<ShareLinkCreated>(`/analysis/${analysisId}/share`, { expires_in_days: expiresInDays })
  return data
}

export async function getShareLinks(analysisId: number) {
  const { data } = await api.get<ShareLinkSummary[]>(`/analysis/${analysisId}/share`)
  return data
}

export async function revokeShareLink(analysisId: number, shareId: number) {
  await api.delete(`/analysis/${analysisId}/share/${shareId}`)
}

export async function getPublicSharedAnalysis(token: string) {
  const { data } = await api.get<PublicSharedAnalysis>(`/public/analysis/${encodeURIComponent(token)}`)
  return data
}