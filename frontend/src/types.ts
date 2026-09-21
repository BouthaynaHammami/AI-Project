export type ModalType = 'signup' | 'login' | 'settings' | null
export type HistoryAnalysis = { id: number; question: string; answer: string; chartConfig: string | null; createdAt: string }
export type HistoryEntry = { id: number; file: string; datasetId: number; question: string; answer: string; chartConfig: string | null; date: string; analyses: HistoryAnalysis[] }
export type Message = { id: number; role: 'user' | 'assistant'; content: string; timestamp: string }
export type ChartConfig = { title: string; labels: string[]; values: number[] }