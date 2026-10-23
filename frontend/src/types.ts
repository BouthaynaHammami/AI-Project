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
	generatedCode: string | null
	codeExplanation: string | null
	codeRetried: boolean
	feedback: FeedbackValue | null
	conversationId: number | null
	conversationTitle: string | null
	date: string
	analysisId: number | null
	title: string | null
	isFavorite: boolean
}
export type FeedbackValue = { rating: -1 | 1; comment: string | null }
export type Message = {
	id: number
	analysisId?: number
	role: 'user' | 'assistant'
	content: string
	timestamp: string
	chartConfig?: string | null
	resultData?: string | null
	resultTable?: { headers: string[]; rows: string[][] }
	generatedCode?: string | null
	codeExplanation?: string | null
	codeRetried?: boolean
	feedback?: FeedbackValue | null
}
export type ChartType = 'bar' | 'line' | 'pie' | 'scatter'
export type ChartSeries = { name: string; values: number[] }
export type ChartConfig = {
	title: string
	labels: string[]
	values?: number[]
	series?: ChartSeries[]
	type?: ChartType
	x_label?: string
	y_label?: string
}