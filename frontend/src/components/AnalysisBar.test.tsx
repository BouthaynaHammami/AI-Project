import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AnalysisBar } from './AnalysisBar'

const uploadFiles = vi.hoisted(() => vi.fn())
vi.mock('../services/fileService', () => ({ uploadFiles }))
vi.mock('./SuggestedQuestions', () => ({
  SuggestedQuestions: ({
    datasetIds,
    onSelect,
  }: {
    datasetIds: number[]
    onSelect: (question: string) => void
  }) => (
    <button type="button" onClick={() => onSelect('Quel produit génère le plus de ventes ?')}>
      Suggestions pour {datasetIds.join(',')}
    </button>
  ),
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('AnalysisBar', () => {
  it('keeps analysis disabled until a question or file is selected', () => {
    render(<AnalysisBar onAnalyze={vi.fn()} />)
    expect(screen.getByRole('button', { name: "Lancer l'analyse" }).hasAttribute('disabled')).toBe(true)
    fireEvent.change(screen.getByPlaceholderText('Posez une question sur vos données...'), { target: { value: 'Total des ventes ?' } })
    expect(screen.getByRole('button', { name: "Lancer l'analyse" }).hasAttribute('disabled')).toBe(false)
  })

  it('shows suggestions after upload and starts analysis when a suggestion is selected', async () => {
    const onAnalyze = vi.fn()
    uploadFiles.mockResolvedValue([{ dataset_id: 3, filename: 'ventes.csv' }])
    const { container } = render(<AnalysisBar onAnalyze={onAnalyze} />)
    const file = new File(['region,sales\nNord,10'], 'ventes.csv', { type: 'text/csv' })
    fireEvent.change(container.querySelector('input[type="file"]')!, { target: { files: [file] } })
    await waitFor(() => expect(screen.getByText('ventes.csv')).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: "Lancer l'analyse" }))
    await waitFor(() => expect(uploadFiles).toHaveBeenCalledWith([file]))
    expect(screen.getByRole('button', { name: 'Suggestions pour 3' })).toBeTruthy()
    expect(onAnalyze).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Suggestions pour 3' }))
    await waitFor(() => expect(onAnalyze).toHaveBeenCalledWith(
      [{ dataset_id: 3, filename: 'ventes.csv' }],
      'Quel produit génère le plus de ventes ?',
    ))
    expect(uploadFiles).toHaveBeenCalledTimes(1)
  })

  it('rejects unsupported files and displays upload failures', async () => {
    const { container } = render(<AnalysisBar onAnalyze={vi.fn()} />)
    const unsupported = new File(['x'], 'notes.txt', { type: 'text/plain' })
    fireEvent.change(container.querySelector('input[type="file"]')!, { target: { files: [unsupported] } })
    expect(screen.getByText(/Format non supporté/)).toBeTruthy()

    const csv = new File(['a,b\n1,2'], 'data.csv', { type: 'text/csv' })
    uploadFiles.mockRejectedValue(new Error('upload failed'))
    fireEvent.change(container.querySelector('input[type="file"]')!, { target: { files: [csv] } })
    await waitFor(() => expect(screen.getByText('data.csv')).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: "Lancer l'analyse" }))
    await waitFor(() => expect(screen.getByText('Une erreur inattendue est survenue.')).toBeTruthy())
  })
})
