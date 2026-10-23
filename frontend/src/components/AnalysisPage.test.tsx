import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AnalysisPage } from './AnalysisPage'
import type { DatasetPreview } from '../services/fileService'

const exportApi = vi.hoisted(() => ({ exportAnalysis: vi.fn() }))
vi.mock('../services/analysisService', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../services/analysisService')>()),
  exportAnalysis: exportApi.exportAnalysis,
}))

vi.mock('./SuggestedQuestions', () => ({
  SuggestedQuestions: () => <div>Suggestions de test</div>,
}))

const dataset = (filename: string, overrides: Partial<DatasetPreview> = {}): DatasetPreview => ({
  dataset_id: 1,
  id: 1,
  filename,
  row_count: 12,
  column_count: 2,
  file_size_bytes: 2048,
  page_count: null,
  column_names: ['region', 'sales'],
  preview: [{ region: 'Nord', sales: 10 }, { region: 'Sud', sales: 20 }],
  pii_report: { columns: [], column_count: 0, values_touched: 0 },
  pii_preferences: {},
  ...overrides,
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('AnalysisPage', () => {
  it('renders metrics, dataset names, saved charts and assistant insight', () => {
    render(
      <AnalysisPage
        datasets={[dataset('ventes.csv'), dataset('budget.xlsx', { dataset_id: 2, id: 2, row_count: 8 })]}
        firstQuestion="Comparez les ventes"
        messages={[{ id: 1, role: 'user', content: 'Comparez', timestamp: '10:00' }, { id: 2, role: 'assistant', content: 'Le Nord progresse.', timestamp: '10:01' }]}
        isAnalyzing={false}
        chartConfig={JSON.stringify({ title: 'Ventes', labels: ['Nord', 'Sud'], values: [10, 20] })}
        onAsk={vi.fn()}
        onAddFiles={vi.fn().mockResolvedValue(undefined)}
      />,
    )
    expect(screen.getAllByText('20').length).toBeGreaterThan(0)
    expect(screen.getByText('4')).toBeTruthy()
    expect(screen.getByText('ventes.csv · budget.xlsx')).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Ventes' })).toBeTruthy()
    expect(screen.getAllByText('Le Nord progresse.').length).toBeGreaterThan(0)
  })

  it('does not fabricate a chart from preview values and offers document suggestions', () => {
    const onAsk = vi.fn()
    render(
      <AnalysisPage
        datasets={[dataset('rapport.pdf', { page_count: 3 }), dataset('mesures.csv', { dataset_id: 2, id: 2 })]}
        firstQuestion=""
        messages={[]}
        isAnalyzing={false}
        chartConfig="{malformed"
        onAsk={onAsk}
        onAddFiles={vi.fn().mockResolvedValue(undefined)}
      />,
    )
    expect(screen.getByText('3 pages')).toBeTruthy()
    expect(screen.getByText('Le graphique sera disponible après la première question.')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Résumer le document' }))
    expect(onAsk).toHaveBeenCalledWith(expect.stringContaining('Résume le contenu'), [1, 2])
  })

  it('renders empty and analyzing chat states', () => {
    render(
      <AnalysisPage
        datasets={[dataset('data.csv')]}
        firstQuestion=""
        messages={[]}
        isAnalyzing
        chartConfig={null}
        onAsk={vi.fn()}
        onAddFiles={vi.fn().mockResolvedValue(undefined)}
      />,
    )
    expect(screen.getByText('Aucun résultat enregistré.')).toBeTruthy()
    expect(screen.getByRole('status', { name: 'Analyse en cours' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Analyser' }).hasAttribute('disabled')).toBe(true)
  })

  it('offers PDF and Excel downloads for the latest saved analysis', async () => {
    const blob = new Blob(['rapport'])
    exportApi.exportAnalysis.mockResolvedValue({
      blob,
      filename: 'analyse-7-resultat.pdf',
    })
    const createObjectURL = vi.fn(() => 'blob:export')
    vi.stubGlobal('URL', {
      createObjectURL,
      revokeObjectURL: vi.fn(),
    })
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)

    render(
      <AnalysisPage
        datasets={[dataset('ventes.csv')]}
        conversationId={3}
        firstQuestion="Meilleur produit ?"
        messages={[{
          id: 7,
          analysisId: 7,
          role: 'assistant',
          content: 'Premium.',
          timestamp: '10:00',
        }]}
        isAnalyzing={false}
        chartConfig={null}
        onAsk={vi.fn()}
        onAddFiles={vi.fn().mockResolvedValue(undefined)}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Exporter' }))
    fireEvent.click(screen.getByRole('menuitem', { name: 'PDF' }))

    await vi.waitFor(() => {
      expect(exportApi.exportAnalysis).toHaveBeenCalledWith(7, 'pdf')
    })
    expect(createObjectURL).toHaveBeenCalledWith(blob)
    expect(HTMLAnchorElement.prototype.click).toHaveBeenCalledOnce()
  })
})
