import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ChatWindow } from './ChatWindow'

const feedbackApi = vi.hoisted(() => ({
  saveFeedback: vi.fn(),
  deleteFeedback: vi.fn(),
}))
vi.mock('../services/analysisService', () => feedbackApi)

afterEach(cleanup)

describe('ChatWindow conversations', () => {
  it('starts a fresh conversation without submitting a question', () => {
    const onNewConversation = vi.fn()
    render(
      <ChatWindow
        messages={[]}
        isAnalyzing={false}
        conversationId={23}
        onAsk={vi.fn()}
        onAddFiles={vi.fn().mockResolvedValue(undefined)}
        onNewConversation={onNewConversation}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Nouvelle conversation' }))
    expect(onNewConversation).toHaveBeenCalledOnce()
  })
})

describe('ChatWindow generated code', () => {
  it('shows escaped executable code, explanation, retry badge and copy action', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText },
    })
    render(
      <ChatWindow
        messages={[{
          id: 2,
          role: 'assistant',
          content: 'Résultat calculé.',
          timestamp: '10:00',
          generatedCode: "print('<script>')",
          codeExplanation: 'Le code affiche le résultat calculé.',
          codeRetried: true,
        }]}
        isAnalyzing={false}
        onAsk={vi.fn()}
        onAddFiles={vi.fn().mockResolvedValue(undefined)}
      />,
    )

    fireEvent.click(screen.getByText('Voir le code généré'))
    expect(screen.getByText("print('<script>')").tagName).toBe('CODE')
    expect(screen.getByText('Corrigé automatiquement')).toBeTruthy()
    expect(screen.getByText('Le code affiche le résultat calculé.')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Copier le code généré' }))

    expect(writeText).toHaveBeenCalledWith("print('<script>')")
    expect(await screen.findByRole('button', { name: 'Code généré copié' })).toBeTruthy()
  })

  it('stores and restores a response vote with an optional reason', async () => {
    feedbackApi.saveFeedback.mockImplementation(async (_id: number, payload: { rating: -1 | 1; comment: string | null }) => ({
      id: 1,
      ...payload,
    }))
    const { rerender } = render(
      <ChatWindow
        messages={[{
          id: 2,
          analysisId: 42,
          role: 'assistant',
          content: 'Réponse à évaluer.',
          timestamp: '10:00',
          feedback: null,
        }]}
        isAnalyzing={false}
        onAsk={vi.fn()}
        onAddFiles={vi.fn().mockResolvedValue(undefined)}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Mauvaise réponse' }))
    await screen.findByRole('combobox', { name: "Que s'est-il passé ?" })
    expect(feedbackApi.saveFeedback).toHaveBeenCalledWith(42, { rating: -1, comment: null })
    fireEvent.change(screen.getByRole('combobox', { name: "Que s'est-il passé ?" }), {
      target: { value: 'Mauvais chiffre' },
    })
    await screen.findByRole('combobox', { name: "Que s'est-il passé ?" })
    expect(feedbackApi.saveFeedback).toHaveBeenLastCalledWith(42, {
      rating: -1,
      comment: 'Mauvais chiffre',
    })

    rerender(
      <ChatWindow
        messages={[{
          id: 2,
          analysisId: 42,
          role: 'assistant',
          content: 'Réponse à évaluer.',
          timestamp: '10:00',
          feedback: { rating: -1, comment: 'Mauvais chiffre' },
        }]}
        isAnalyzing={false}
        onAsk={vi.fn()}
        onAddFiles={vi.fn().mockResolvedValue(undefined)}
      />,
    )
    expect(screen.getByRole('button', { name: 'Mauvaise réponse' }).getAttribute('aria-pressed')).toBe('true')
    expect((screen.getByRole('combobox', { name: "Que s'est-il passé ?" }) as HTMLSelectElement).value).toBe('Mauvais chiffre')
  })

  it('removes a vote when the selected reaction is clicked again', async () => {
    feedbackApi.deleteFeedback.mockResolvedValue(undefined)
    render(
      <ChatWindow
        messages={[{
          id: 2,
          analysisId: 42,
          role: 'assistant',
          content: 'Réponse déjà notée.',
          timestamp: '10:00',
          feedback: { rating: 1, comment: null },
        }]}
        isAnalyzing={false}
        onAsk={vi.fn()}
        onAddFiles={vi.fn().mockResolvedValue(undefined)}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Bonne réponse' }))

    await vi.waitFor(() => {
      expect(feedbackApi.deleteFeedback).toHaveBeenCalledWith(42)
      expect(screen.getByRole('button', { name: 'Bonne réponse' }).getAttribute('aria-pressed')).toBe('false')
    })
  })
})
