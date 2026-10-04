export type ModalType = 'signup' | 'login' | 'settings' | null
export type Feedback = {
	id: number
	analysis_id: number
	user_id: number
	rating: 1 | -1
	comment: string | null
	created_at: string
}
export type ConversationTurn = {
	analysisId: number
	question: string
	answer: string
	chartConfig: string | null
	generatedCode: string | null
	codeExplanation: string | null
	codeRetried: boolean
	feedback: Feedback | null
	createdAt: string
}
export type HistoryEntry = {
	id: number
	kind: 'import' | 'discussion'
	file: string
	datasetId: number
	datasetIds: number[]
	question: string
	answer: string
	chartConfig: string | null
	generatedCode: string | null
	codeExplanation: string | null
	codeRetried: boolean
	feedback: Feedback | null
	conversationId: number | null
	conversationTitle: string | null
	conversationMessages?: ConversationTurn[]
	date: string
}
export type Message = { id: number; analysisId?: number; role: 'user' | 'assistant'; content: string; timestamp: string; chartConfig?: string | null; generatedCode?: string | null; codeExplanation?: string | null; codeRetried?: boolean; feedback?: Feedback | null }
export type ChartType = 'bar' | 'line' | 'pie' | 'scatter'
export type ChartSeries = { name: string; values: number[] }
export type ChartConfig = {
	type?: ChartType
	title: string
	x_label?: string
	y_label?: string
	labels: string[]
	series?: ChartSeries[]
	values?: number[]
}