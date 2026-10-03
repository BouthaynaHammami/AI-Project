export type ModalType = 'signup' | 'login' | 'settings' | null
export type HistoryEntry = {
	id: number
	kind: 'import' | 'discussion'
	file: string
	datasetId: number
	datasetIds: number[]
	question: string
	answer: string
	chartConfig: string | null
	date: string
}
export type Message = { id: number; role: 'user' | 'assistant'; content: string; timestamp: string; chartConfig?: string | null }
export type ChartConfig = { title: string; labels: string[]; values: number[] }