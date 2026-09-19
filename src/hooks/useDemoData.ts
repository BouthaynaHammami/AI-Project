import { useState } from 'react'
import type { HistoryEntry, Message } from '../types'
import { mockAnalysis } from '../services/api'

export const useDemoData = () => {
  const [history] = useState<HistoryEntry[]>([
    { id: 1, file: 'student-performance.csv', question: 'Quels facteurs influencent les scores ?', date: 'Aujourd’hui, 10:42' },
    { id: 2, file: 'sales-q3.xlsx', question: 'Compare les ventes par région', date: 'Hier, 16:18' },
    { id: 3, file: 'marketing-leads.csv', question: 'Quel canal convertit le mieux ?', date: '12 sept. 2024' },
    { id: 4, file: 'budget-2024.xlsx', question: 'Montre les dépenses mensuelles', date: '08 sept. 2024' },
  ])
  const [messages, setMessages] = useState<Message[]>([{ id: 1, role: 'user', content: 'Quels facteurs influencent les scores des étudiants ?', timestamp: '10:42' }, { id: 2, role: 'assistant', content: mockAnalysis.content, timestamp: '10:42' }])
  const askQuestion = (question: string) => {
    const time = new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
    setMessages((current) => [...current, { id: Date.now(), role: 'user', content: question, timestamp: time }, { id: Date.now() + 1, role: 'assistant', content: 'Analyse terminée. Les données indiquent une corrélation positive entre l’assiduité et les scores. Le groupe le plus assidu dépasse la moyenne de 9 points.', timestamp: time }])
  }
  return { history, messages, askQuestion }
}