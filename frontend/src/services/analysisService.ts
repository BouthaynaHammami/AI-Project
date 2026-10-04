import { api } from './api'
import type { Feedback } from '../types'

export type AnalysisAnswer = { id: number; conversation_id: number; dataset_id: number; question: string; type: 'text'; content: string; chart_config: string | null; generated_code: string | null; code_explanation: string | null; code_retried: boolean; feedback: Feedback | null; created_at: string }
export type AnalysisHistory = { id: number; conversation_id: number | null; conversation_title: string | null; conversation_dataset_ids: number[]; dataset_id: number; question: string; answer: string; result_type: string; result_data: string | null; chart_config: string | null; generated_code: string | null; code_explanation: string | null; code_retried: boolean; feedback: Feedback | null; created_at: string }
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

export async function askQuestion(datasetIds: number[], question: string, conversationId: number | null = null) {
  const { data } = await api.post<AnalysisAnswer>('/analysis/ask', {
    dataset_ids: datasetIds,
    question,
    conversation_id: conversationId,
  })
  return data
}

export async function getHistory() {
  const { data } = await api.get<AnalysisHistory[]>('/analysis/history')
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