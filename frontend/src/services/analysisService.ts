import { api } from './api'

export type AnalysisAnswer = { id: number; dataset_id: number; question: string; type: 'text'; content: string; created_at: string }
export type AnalysisHistory = { id: number; dataset_id: number; question: string; answer: string; result_type: string; created_at: string }
export async function askQuestion(datasetId: number, question: string) { const { data } = await api.post<AnalysisAnswer>('/analysis/ask', { dataset_id: datasetId, question }); return data }
export async function getHistory() { const { data } = await api.get<AnalysisHistory[]>('/analysis/history'); return data }