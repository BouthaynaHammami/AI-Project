
import { api } from './api'

export type DatasetPreview = {
  dataset_id: number
  id: number
  filename: string
  row_count: number
  column_count: number
  column_names: string[]
  preview: Record<string, unknown>[]
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