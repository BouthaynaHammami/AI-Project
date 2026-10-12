import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AnalysisPage } from './AnalysisPage'
import type { DatasetPreview } from '../services/fileService'

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

afterEach(cleanup)

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
    expect(screen.getByRole('heading', { name: 'Evolution de Ventes' })).toBeTruthy()
    expect(screen.getAllByText('Le Nord progresse.').length).toBeGreaterThan(0)
  })

  it('falls back to numeric chart data and offers document suggestions', () => {
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
    expect(screen.getByRole('heading', { name: 'Evolution de sales' })).toBeTruthy()
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
})
