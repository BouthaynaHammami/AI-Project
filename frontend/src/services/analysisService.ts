import { api } from './api'

export type AnalysisAnswer = { id: number; dataset_id: number; question: string; type: 'text'; content: string; chart_config: string | null; created_at: string }
export type AnalysisHistory = { id: number; dataset_id: number; question: string; answer: string; result_type: string; result_data: string | null; chart_config: string | null; created_at: string }

export async function askQuestion(datasetIds: number[], question: string) {
  const { data } = await api.post<AnalysisAnswer>('/analysis/ask', { dataset_ids: datasetIds, question })
  return data
}

export async function getHistory() {
  const { data } = await api.get<AnalysisHistory[]>('/analysis/history')
  return data
}