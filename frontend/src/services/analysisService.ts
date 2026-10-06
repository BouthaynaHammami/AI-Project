import { api } from './api'
import type { Feedback } from '../types'

export type AnalysisAnswer = { id: number; conversation_id: number; dataset_id: number; question: string; type: 'text'; content: string; chart_config: string | null; generated_code: string | null; code_explanation: string | null; code_retried: boolean; feedback: Feedback | null; created_at: string }
export type AnalysisHistory = { id: number; conversation_id: number | null; conversation_title: string | null; conversation_dataset_ids: number[]; dataset_id: number | null; question: string; answer: string; result_type: string; result_data: string | null; chart_config: string | null; generated_code: string | null; code_explanation: string | null; code_retried: boolean; feedback: Feedback | null; title: string | null; is_favorite: boolean; created_at: string }
export type SuggestedQuestion = {
  question: string
  category: 'classement' | 'evolution' | 'comparaison' | 'repartition' | 'qualite' | 'synthese'
  chart: boolean
}
export type AnalysisSuggestions = {
  suggestions: SuggestedQuestion[]
  source: 'ai' | 'rules' | 'cache'
}
export type AnalysisFeedbackStats = {
  like_rate: number
  total_votes: number
  recent_negative_questions: { question: string; created_at: string }[]
}
export type ShareLinkSummary = {
  id: number
  created_at: string
  expires_at: string
  view_count: number
}
export type CreatedShareLink = {
  id: number
  token: string
  expires_at: string
}
export type PublicSharedAnalysis = {
  question: string
  answer: string
  chart_config: string | null
  created_at: string
}

export async function askQuestion(datasetIds: number[], question: string, conversationId: number | null = null) {
  const { data } = await api.post<AnalysisAnswer>('/analysis/ask', {
    dataset_ids: datasetIds,
    question,
    conversation_id: conversationId,
  })
  return data
}

export type AnalysisHistoryPage = { items: AnalysisHistory[]; total: number; has_more: boolean }

export async function getHistory(
  params: { q?: string; favorite?: boolean; limit?: number; offset?: number } = {},
  signal?: AbortSignal,
) {
  const { data } = await api.get<AnalysisHistoryPage>('/analysis/history', { params, signal })
  return data
}

export async function updateAnalysis(
  analysisId: number,
  patch: { title?: string | null; is_favorite?: boolean },
) {
  const { data } = await api.patch<AnalysisHistory>(`/analysis/${analysisId}`, patch)
  return data
}

export async function deleteAnalysis(analysisId: number) {
  await api.delete(`/analysis/${analysisId}`)
}

export async function restoreAnalysis(analysisId: number) {
  const { data } = await api.post<AnalysisHistory>(`/analysis/${analysisId}/restore`)
  return data
}

export async function saveFeedback(analysisId: number, rating: 1 | -1, comment: string | null) {
  const { data } = await api.put<Feedback>(`/analysis/${analysisId}/feedback`, { rating, comment })
  return data
}

export async function deleteFeedback(analysisId: number) {
  await api.delete(`/analysis/${analysisId}/feedback`)
}

export async function getFeedbackStats() {
  const { data } = await api.get<AnalysisFeedbackStats>('/analysis/stats')
  return data
}

export async function getSuggestions(datasetIds: number[], refresh = false, signal?: AbortSignal) {
  const { data } = await api.get<AnalysisSuggestions>('/analysis/suggestions', {
    params: { dataset_ids: datasetIds.join(','), refresh },
    signal,
  })
  return data
}

export async function exportAnalysis(analysisId: number, format: 'pdf' | 'xlsx') {
  const response = await api.get<Blob>(`/analysis/${analysisId}/export`, {
    params: { format },
    responseType: 'blob',
  })
  const disposition = response.headers['content-disposition'] as string | undefined
  const filename = disposition?.match(/filename="?([^";]+)"?/i)?.[1] ?? `analyse-${analysisId}.${format}`
  return { blob: response.data, filename }
}

export async function createShareLink(analysisId: number, expiresInDays: 1 | 7 | 30) {
  const { data } = await api.post<CreatedShareLink>(`/analysis/${analysisId}/share`, {
    expires_in_days: expiresInDays,
  })
  return data
}

export async function getShareLinks(analysisId: number) {
  const { data } = await api.get<ShareLinkSummary[]>(`/analysis/${analysisId}/share`)
  return data
}

export async function revokeShareLink(analysisId: number, shareId: number) {
  await api.delete(`/analysis/${analysisId}/share/${shareId}`)
}

export async function getPublicSharedAnalysis(token: string): Promise<PublicSharedAnalysis> {
  const baseUrl = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(/\/+$/, '')
  const response = await fetch(
    `${baseUrl}/public/analysis/${encodeURIComponent(token)}`,
    { headers: { Accept: 'application/json' }, cache: 'no-store' },
  )
  if (!response.ok) throw new Error('Cette analyse partagée est introuvable ou n’est plus disponible.')
  return response.json() as Promise<PublicSharedAnalysis>
}