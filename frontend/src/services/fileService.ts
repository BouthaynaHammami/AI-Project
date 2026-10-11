
import { api } from './api'

export type DatasetPreview = {
  dataset_id: number
  id: number
  filename: string
  row_count: number
  column_count: number
  file_size_bytes?: number
  page_count?: number | null
  column_names: string[]
  preview: Record<string, unknown>[]
  profile?: DataProfile | null
  pii_report: PiiReport
  pii_preferences: Record<string, PiiPreference>
}

export type PiiPreference = 'exclude' | 'mask' | 'allow'
export type PiiColumn = {
  name: string
  position: number
  category: string
  values_touched: number
  confidence: 'high' | 'medium'
}
export type PiiReport = {
  columns: PiiColumn[]
  column_count: number
  values_touched: number
}
export type DataProfileColumn = {
  name: string
  position: number
  detected_type: string
  missing_count: number
  missing_percentage: number
  unique_count: number
  statistics?: { min: unknown; max: unknown; mean: unknown; median: unknown }
  date_range?: { min: unknown; max: unknown }
  top_values?: Array<{ value: unknown; count: number }>
}
export type DataProfile = {
  row_count: number
  column_count: number
  duplicate_rows: number
  sampled_rows: number
  columns: DataProfileColumn[]
  alerts: Array<{ type: string; severity: string; column: string; message: string }>
}

// Upload multiple files separately in one request
export async function uploadFiles(files: File[]) {
  const form = new FormData()

  files.forEach((file) => {
    form.append('files', file)
  })

  const { data } = await api.post<DatasetPreview[]>(
    '/files/upload',
    form,
    { headers: { 'Content-Type': 'multipart/form-data' } }
  )

  return data
}

export async function getDatasetPreview(datasetId: number) {
  const { data } = await api.get<DatasetPreview>(
    `/files/${datasetId}/preview`
  )

  return {
    ...data,
    dataset_id: data.id,
  }
}

export type DatasetHistory = {
  id: number
  filename: string
  created_at: string
}

export async function getDatasetHistory() {
  const { data } = await api.get<DatasetHistory[]>(
    '/files/history'
  )

  return data
}

export async function updatePiiPreferences(datasetId: number, preferences: Record<string, PiiPreference>) {
  const { data } = await api.put<Record<string, PiiPreference>>(
    `/files/${datasetId}/pii-preferences`,
    { preferences },
  )
  return data
}

export async function deleteDataset(datasetId: number) {
  await api.delete(`/files/${datasetId}`)
}