export type ModalType = 'signup' | 'login' | 'settings' | null
export type HistoryEntry = { id: number; file: string; question: string; date: string }
export type Message = { id: number; role: 'user' | 'assistant'; content: string; timestamp: string }