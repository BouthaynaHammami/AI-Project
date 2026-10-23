import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { DataPreviewTable } from './DataPreviewTable'
import type { DatasetPreview } from '../services/fileService'

const piiApi = vi.hoisted(() => ({ updatePiiPreferences: vi.fn() }))
vi.mock('../services/fileService', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/fileService')>()
  return { ...actual, updatePiiPreferences: piiApi.updatePiiPreferences }
})

const dataset: DatasetPreview = {
  dataset_id: 7,
  id: 7,
  filename: 'sales.csv',
  row_count: 4,
  column_count: 2,
  column_names: ['amount', 'created_at'],
  preview: [{ amount: 10, created_at: '2025-01-01' }],
  profile: {
    row_count: 4,
    column_count: 2,
    duplicate_rows: 1,
    sampled_rows: 4,
    columns: [
      {
        name: 'amount',
        position: 0,
        detected_type: 'numérique',
        missing_count: 2,
        missing_percentage: 50,
        unique_count: 2,
        statistics: { min: 10, max: 20, mean: 15, median: 15 },
      },
      {
        name: 'created_at',
        position: 1,
        detected_type: 'date',
        missing_count: 0,
        missing_percentage: 0,
        unique_count: 2,
        date_range: { min: '2025-01-01T00:00:00+00:00', max: '2025-01-02T00:00:00+00:00' },
      },
    ],
    alerts: [
      {
        type: 'date_stored_as_text',
        severity: 'warning',
        column: 'created_at',
        message: 'La colonne « created_at » contient des dates stockées comme texte.',
      },
    ],
  },
  pii_report: { columns: [], column_count: 0, values_touched: 0 },
  pii_preferences: {},
}

afterEach(cleanup)

describe('DataPreviewTable', () => {
  it('shows sensitive-column counts and persists the selected privacy action', async () => {
    piiApi.updatePiiPreferences.mockImplementation(async (_datasetId: number, preferences: Record<string, string>) => preferences)
    render(
      <DataPreviewTable datasets={[{
        ...dataset,
        pii_report: {
          column_count: 3,
          values_touched: 12,
          columns: [
            { name: 'email', position: 0, category: 'email', values_touched: 4, confidence: 'high' },
            { name: 'iban', position: 1, category: 'iban', values_touched: 4, confidence: 'high' },
            { name: 'contact', position: 2, category: 'téléphone', values_touched: 4, confidence: 'medium' },
          ],
        },
      }]} />,
    )

    expect(screen.getByText('3 colonnes sensibles détectées')).toBeTruthy()
    expect(screen.getByText(/email · 4 valeurs · confiance élevée/)).toBeTruthy()
    const action = screen.getByRole('combobox', { name: 'Action pour email' })
    fireEvent.change(action, { target: { value: 'exclude' } })

    await vi.waitFor(() => {
      expect(piiApi.updatePiiPreferences).toHaveBeenCalledWith(7, { email: 'exclude' })
      expect((screen.getByRole('combobox', { name: 'Action pour email' }) as HTMLSelectElement).value).toBe('exclude')
    })
  })

  it('renders the uploaded table and its data quality profile', () => {
    render(<DataPreviewTable datasets={[dataset]} />)

    expect(screen.getByRole('heading', { name: 'sales.csv' })).toBeTruthy()
    expect(screen.getByRole('region', { name: 'Profil de qualité des données' })).toBeTruthy()
    expect(screen.getByText('Lignes en doublon')).toBeTruthy()
    expect(screen.getByText(/Moy\.\s*15/)).toBeTruthy()
    expect(screen.getByText('2025-01-01T00:00:00+00:00 → 2025-01-02T00:00:00+00:00')).toBeTruthy()
    expect(screen.getByText('La colonne « created_at » contient des dates stockées comme texte.')).toBeTruthy()
    expect(screen.getByRole('img', { name: '50 % de valeurs manquantes' })).toBeTruthy()
  })

  it('keeps the table preview available when a dataset has no profile', () => {
    const { profile: _profile, ...withoutProfile } = dataset
    render(<DataPreviewTable datasets={[{ ...withoutProfile, dataset_id: 8, id: 8, filename: 'report.pdf' }]} />)

    expect(screen.getByRole('heading', { name: 'report.pdf' })).toBeTruthy()
    expect(screen.queryByText('Qualité des données')).toBeNull()
  })
})
