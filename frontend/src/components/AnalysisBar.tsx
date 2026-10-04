
import {
  ArrowUp,
  FileImage,
  FileSpreadsheet,
  FileText,
  FileUp,
  Paperclip,
  X,
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import * as XLSX from 'xlsx'

import { getApiError } from '../services/api'
import { uploadFiles, type DatasetPreview } from '../services/fileService'
import { getSuggestions } from '../services/analysisService'
import type { SuggestedQuestion as SuggestedQuestionData } from '../services/analysisService'
import { SuggestedQuestions } from './SuggestedQuestions'

type Props = {
  onAnalyze: (datasets: DatasetPreview[], question: string) => void
}

type FileKind = 'csv' | 'excel' | 'pdf' | 'word' | 'image'

type SelectedFilePreview = {
  id: string
  file: File
  kind: FileKind
  rowCount?: number
  columnCount?: number
  columns?: string[]
  previewRows?: Record<string, unknown>[]
  previewUrl?: string
}

const ACCEPT_STRING = '.pdf,.doc,.docx,.csv,.xls,.xlsx,.png,.jpg,.jpeg'

const isValidFile = (file: File) => {
  const name = file.name.toLowerCase()
  const mime = file.type.toLowerCase()

  if (name.endsWith('.pdf') || mime.includes('pdf')) return true
  if (name.endsWith('.doc') || name.endsWith('.docx') || mime.includes('word')) return true
  if (name.endsWith('.csv') || mime.includes('csv')) return true
  if (name.endsWith('.xls') || name.endsWith('.xlsx') || mime.includes('excel') || mime.includes('sheet')) return true
  if (name.endsWith('.png') || name.endsWith('.jpg') || name.endsWith('.jpeg') || mime.includes('image')) return true

  return false
}

const getFileKind = (file: File): FileKind => {
  const name = file.name.toLowerCase()
  const mime = file.type.toLowerCase()

  if (name.endsWith('.pdf') || mime.includes('pdf')) return 'pdf'
  if (name.endsWith('.doc') || name.endsWith('.docx') || mime.includes('word')) return 'word'
  if (name.endsWith('.csv') || mime.includes('csv')) return 'csv'
  if (name.endsWith('.xls') || name.endsWith('.xlsx') || mime.includes('excel') || mime.includes('sheet')) return 'excel'
  if (name.endsWith('.png') || name.endsWith('.jpg') || name.endsWith('.jpeg') || mime.includes('image')) return 'image'
  return 'pdf'
}

const getFileIcon = (kind: FileKind) => {
  if (kind === 'image') return FileImage
  if (kind === 'excel' || kind === 'csv') return FileSpreadsheet
  if (kind === 'pdf' || kind === 'word') return FileText
  return FileUp
}

const parseExcelData = async (file: File) => {
  const workbook = XLSX.read(await file.arrayBuffer(), { type: 'array' })
  const sheetName = workbook.SheetNames[0]
  const sheet = workbook.Sheets[sheetName]
  const rows = XLSX.utils.sheet_to_json(sheet, { header: 1, raw: false }) as Array<Array<string | number | boolean | null>>

  if (!rows.length) {
    return { columns: [], previewRows: [], rowCount: 0, columnCount: 0 }
  }

  const columns = (rows[0] as Array<string | number | boolean | null>).map((header, index) => String(header ?? `Colonne ${index + 1}`))
  const previewRows = rows.slice(1, 6).map((row) => {
    const record: Record<string, unknown> = {}
    columns.forEach((column, index) => {
      record[column] = row[index] ?? ''
    })
    return record
  })

  return {
    columns,
    previewRows,
    rowCount: Math.max(rows.length - 1, 0),
    columnCount: columns.length,
  }
}

const buildPreview = async (file: File): Promise<SelectedFilePreview> => {
  const kind = getFileKind(file)

  if (kind === 'excel') {
    const excelData = await parseExcelData(file)
    return {
      id: `${file.name}-${file.size}-${file.lastModified}`,
      file,
      kind,
      ...excelData,
    }
  }

  if (kind === 'pdf') {
    return {
      id: `${file.name}-${file.size}-${file.lastModified}`,
      file,
      kind,
    }
  }

  if (kind === 'image') {
    return {
      id: `${file.name}-${file.size}-${file.lastModified}`,
      file,
      kind,
      previewUrl: URL.createObjectURL(file),
    }
  }

  return {
    id: `${file.name}-${file.size}-${file.lastModified}`,
    file,
    kind,
  }
}

export function AnalysisBar({ onAnalyze }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const suggestionAbortRef = useRef<AbortController | null>(null)

  const [files, setFiles] = useState<File[]>([])
  const [previews, setPreviews] = useState<SelectedFilePreview[]>([])
  const [question, setQuestion] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [uploadedItems, setUploadedItems] = useState<Array<{ fileId: string; dataset: DatasetPreview }>>([])
  const uploadedDatasets = uploadedItems.map((item) => item.dataset)
  const uploadedFileIds = uploadedItems.map((item) => item.fileId)
  const [suggestions, setSuggestions] = useState<SuggestedQuestionData[]>([])
  const [suggestionsLoading, setSuggestionsLoading] = useState(false)
  const [suggestionsEmpty, setSuggestionsEmpty] = useState(false)

  useEffect(() => () => suggestionAbortRef.current?.abort(), [])

  const chooseFiles = async (candidates: FileList | null) => {
    if (!candidates) return

    suggestionAbortRef.current?.abort()
    setSuggestions([])
    setSuggestionsLoading(false)
    setSuggestionsEmpty(false)
    const newFiles = Array.from(candidates)
    const invalidFile = newFiles.find((file) => !isValidFile(file))

    if (invalidFile) {
      setError('Format non supporté. Utilisez un fichier PDF, Word, CSV, Excel, PNG ou JPG.')
      if (inputRef.current) inputRef.current.value = ''
      return
    }

    const preparedFiles = await Promise.all(newFiles.map(buildPreview))

    setError('')
    setPreviews((previousPreviews) => {
      const combinedPreviews = [...previousPreviews, ...preparedFiles]
      return combinedPreviews.filter(
        (preview, index, self) =>
          index ===
          self.findIndex(
            (other) =>
              other.file.name === preview.file.name &&
              other.file.size === preview.file.size &&
              other.file.lastModified === preview.file.lastModified
          )
      )
    })

    setFiles((previousFiles) => {
      const combinedFiles = [...previousFiles, ...newFiles]
      return combinedFiles.filter(
        (file, index, self) =>
          index ===
          self.findIndex(
            (other) =>
              other.name === file.name &&
              other.size === file.size &&
              other.lastModified === file.lastModified
          )
      )
    })

    if (inputRef.current) inputRef.current.value = ''
  }

  const removeFile = (indexToRemove: number) => {
    const removedPreview = previews[indexToRemove]
    if (removedPreview) {
      suggestionAbortRef.current?.abort()
      setSuggestionsLoading(false)
      setUploadedItems((previous) => previous.filter((item) => item.fileId !== removedPreview.id))
    }
    setFiles((previousFiles) => previousFiles.filter((_, index) => index !== indexToRemove))
    setPreviews((previousPreviews) => previousPreviews.filter((_, index) => index !== indexToRemove))
    setSuggestions([])
    setSuggestionsEmpty(false)
    setError('')
  }

  const submit = async () => {
    if (files.length === 0 && uploadedDatasets.length === 0 && !question.trim()) return

    setLoading(true)
    setError('')

    try {
      const newFiles = files.filter((file) => {
        const id = `${file.name}-${file.size}-${file.lastModified}`
        return !uploadedFileIds.includes(id)
      })
      const newlyUploaded = newFiles.length > 0 ? await uploadFiles(newFiles) : []
      const datasets = [...uploadedDatasets, ...newlyUploaded]
      if (newlyUploaded.length > 0) {
        setUploadedItems((previous) => [
          ...previous,
          ...newFiles.map((file, index) => ({
            fileId: `${file.name}-${file.size}-${file.lastModified}`,
            dataset: newlyUploaded[index],
          })),
        ])
      }

      if (question.trim()) {
        onAnalyze(datasets, question.trim())
      } else if (datasets.length > 0) {
        await loadSuggestions(datasets.map((dataset) => dataset.dataset_id))
      }
    } catch (uploadError) {
      setError(getApiError(uploadError))
    } finally {
      setLoading(false)
    }
  }

  const loadSuggestions = async (datasetIds: number[], refresh = false) => {
    suggestionAbortRef.current?.abort()
    const controller = new AbortController()
    suggestionAbortRef.current = controller
    setSuggestionsLoading(true)
    setSuggestionsEmpty(false)
    setError('')
    try {
      const result = await getSuggestions(datasetIds, refresh, controller.signal)
      if (!controller.signal.aborted) {
        setSuggestions(result.suggestions)
        setSuggestionsEmpty(result.suggestions.length === 0)
      }
    } catch (suggestionError) {
      if (!controller.signal.aborted) {
        setSuggestions([])
        setSuggestionsEmpty(true)
        setError(getApiError(suggestionError))
      }
    } finally {
      if (!controller.signal.aborted) setSuggestionsLoading(false)
    }
  }

  const submitSuggestion = (suggestion: string) => {
    if (loading || uploadedDatasets.length === 0) return
    setQuestion(suggestion)
    setSuggestions([])
    onAnalyze(uploadedDatasets, suggestion)
  }

  const renderPreview = (preview: SelectedFilePreview, index: number) => {
    if (preview.kind === 'excel') {
      return (
        <div className="file-preview-content file-preview-table-wrap">
          <div className="file-preview-summary">
            <span>{preview.rowCount ?? 0} lignes</span>
            <span>{preview.columnCount ?? 0} colonnes</span>
          </div>
          {preview.columns && preview.columns.length > 0 && (
            <div className="file-preview-columns">
              {preview.columns.map((column, index) => (
                <span key={`${column}-${index}`} className="file-preview-column-chip">{column}</span>
              ))}
            </div>
          )}
          {preview.previewRows && preview.previewRows.length > 0 && (
            <div className="file-preview-table-wrapper">
              <table className="file-preview-table">
                <thead>
                  <tr>
                    {preview.columns?.map((column) => (
                      <th key={column}>{column}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {preview.previewRows.map((row, index) => (
                    <tr key={`${preview.file.name}-${index}`}>
                      {preview.columns?.map((column) => (
                        <td key={`${column}-${index}`}>{String(row[column] ?? '')}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )
    }

    if (preview.kind === 'pdf' || preview.kind === 'word') return null

    if (preview.kind === 'image' && preview.previewUrl) {
      return (
        <div className="file-preview-content file-preview-image-wrap">
          <img src={preview.previewUrl} alt={preview.file.name} className="file-preview-image" />
          <button type="button" className="remove-image-preview-button" onClick={() => removeFile(index)} disabled={loading} aria-label={`Supprimer ${preview.file.name}`} title={`Supprimer ${preview.file.name}`}>
            <X size={14} />
          </button>
        </div>
      )
    }

    return null
  }

  return (
    <section className="analysis-bar">
      <div className="analysis-bar-top">
        <span className="section-kicker">NOUVELLE ANALYSE</span>
        <span className="analysis-bar-hint">Posez une question sur vos données</span>
      </div>

      <div className="analysis-chat-row">
        <input
          className="question-input"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              void submit()
            }
          }}
          placeholder="Posez une question sur vos données..."
        />

        <button className="send-button analysis-send" aria-label={question.trim() ? "Lancer l'analyse" : "Importer et obtenir des suggestions"} title={question.trim() ? "Lancer l'analyse" : "Importer le fichier et afficher des questions suggérées"} onClick={() => void submit()} disabled={loading || (files.length === 0 && uploadedDatasets.length === 0 && !question.trim())}>
          <ArrowUp size={17} />
        </button>
      </div>
      {(uploadedDatasets.length > 0 || suggestionsLoading || suggestions.length > 0 || suggestionsEmpty) && (
        <SuggestedQuestions
          suggestions={suggestions}
          loading={suggestionsLoading}
          onSelect={submitSuggestion}
          onRefresh={() => void loadSuggestions(uploadedDatasets.map((dataset) => dataset.dataset_id), true)}
          empty={suggestionsEmpty}
        />
      )}

      <div className="analysis-file-row">
        <button type="button" className="icon-button" onClick={() => inputRef.current?.click()} aria-label="Importer des fichiers" title="Importer des fichiers" disabled={loading}>
          <Paperclip size={17} />
        </button>

        {previews.length > 0 ? (
          <div className="analysis-selected-files">
            {previews.map((preview, index) => {
              const Icon = getFileIcon(preview.kind)
              return (
                <div className="selected-file selected-file-chip" key={preview.id}>
                  <div className="selected-file-main">
                    <span className="selected-file-icon"><Icon size={15} /></span>
                    <span className="selected-file-name" title={preview.file.name}>{preview.file.name}</span>
                  </div>
                  <button type="button" className="remove-file-button" onClick={() => removeFile(index)} disabled={loading} aria-label={`Supprimer ${preview.file.name}`} title={`Supprimer ${preview.file.name}`}>
                    <X size={14} />
                  </button>
                </div>
              )
            })}
          </div>
        ) : (
          <span className="file-hint">{loading ? 'Import en cours...' : 'Ajouter un fichier PDF, Word, CSV, Excel, image ou autre document'}</span>
        )}

        <input ref={inputRef} type="file" accept={ACCEPT_STRING} multiple hidden onChange={(event) => { void chooseFiles(event.target.files) }} />
      </div>

      {previews.some((preview) => preview.kind === 'excel' || preview.kind === 'image') && (
        <div className="analysis-file-previews">
          {previews.map((preview, index) => {
            const content = renderPreview(preview, index)
            return content ? <div className="analysis-file-preview" key={preview.id}>{content}</div> : null
          })}
        </div>
      )}

      {error && <div className="error-banner">{error}</div>}
    </section>
  )
}