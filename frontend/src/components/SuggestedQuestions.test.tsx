import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { SuggestedQuestions } from './SuggestedQuestions'

const getSuggestions = vi.hoisted(() => vi.fn())
vi.mock('../services/analysisService', () => ({ getSuggestions }))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('SuggestedQuestions', () => {
  it('loads data-specific questions, refreshes and sends a selected question', async () => {
    getSuggestions
      .mockResolvedValueOnce({
        suggestions: [{ question: 'Quel produit a le plus grand montant ?', category: 'classement', chart: true }],
        source: 'ai',
      })
      .mockResolvedValueOnce({
        suggestions: [{ question: 'Comment évolue le montant par mois ?', category: 'evolution', chart: false }],
        source: 'ai',
      })
    const onSelect = vi.fn()
    render(<SuggestedQuestions datasetIds={[3, 8]} onSelect={onSelect} />)

    const first = await screen.findByRole('button', { name: /Quel produit a le plus grand montant/ })
    expect(first.textContent).toContain('Graphique')
    fireEvent.click(first)
    expect(onSelect).toHaveBeenCalledWith('Quel produit a le plus grand montant ?')

    fireEvent.click(screen.getByRole('button', { name: 'Autres idées' }))
    await waitFor(() => expect(screen.getByRole('button', { name: /Comment évolue le montant/ })).toBeTruthy())
    expect(getSuggestions).toHaveBeenNthCalledWith(1, [3, 8], false, expect.any(AbortSignal))
    expect(getSuggestions).toHaveBeenNthCalledWith(2, [3, 8], true, expect.any(AbortSignal))
  })
})
