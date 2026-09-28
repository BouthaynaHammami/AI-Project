
import { ArrowUp, CheckCircle2, FileUp, Paperclip, X } from 'lucide-react'
import { useRef, useState } from 'react'

import { getApiError } from '../services/api'
import { uploadFiles, type DatasetPreview } from '../services/fileService'
type Props = {
  onAnalyze: (
    datasets: DatasetPreview[],
    question: string
  ) => void
}

export function AnalysisBar({ onAnalyze }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)

  const [files, setFiles] = useState<File[]>([])
  const [question, setQuestion] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  // Select multiple CSV or Excel files
  const chooseFiles = (candidates: FileList | null) => {
    if (!candidates) return

    const newFiles = Array.from(candidates)

    const invalidFile = newFiles.find(
      (file) => !/\.(csv|xlsx)$/i.test(file.name)
    )

    if (invalidFile) {
      setError('Utilisez uniquement des fichiers .csv ou .xlsx.')
      if (inputRef.current) {
        inputRef.current.value = ''
      }
      return
    }

    setError('')

    setFiles((previousFiles) => {
      const combinedFiles = [...previousFiles, ...newFiles]

      // Prevent duplicate files
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

    // Allow selecting the same file again later
    if (inputRef.current) {
      inputRef.current.value = ''
    }
  }

  // Remove one file using its index
  const removeFile = (indexToRemove: number) => {
    setFiles((previousFiles) =>
      previousFiles.filter((_, index) => index !== indexToRemove)
    )

    setError('')
  }

  // Submit the question and selected files
  const submit = async () => {
    if (files.length === 0 && !question.trim()) return

    setLoading(true)
    setError('')

    try {
           const datasets = files.length > 0 ? await uploadFiles(files) : []
      onAnalyze(datasets, question.trim())
    } catch (uploadError) {
      setError(getApiError(uploadError))
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="analysis-bar">
      <div className="analysis-bar-top">
        <span className="section-kicker">NOUVELLE ANALYSE</span>
        <span className="analysis-bar-hint">
          Posez une question sur vos données
        </span>
      </div>

      {/* Selected files */}
      {files.length > 0 && (
        <div className="analysis-selected-files">
          {files.map((file, index) => (
            <div
              className="selected-file"
              key={`${file.name}-${file.size}-${file.lastModified}`}
            >
              <FileUp size={15} />

              <span className="selected-file-name">
                {file.name}
              </span>

              <CheckCircle2 size={14} />

              <button
                type="button"
                className="remove-file-button"
                onClick={() => removeFile(index)}
                disabled={loading}
                aria-label={`Supprimer ${file.name}`}
                title="Supprimer ce fichier"
              >
                <X size={14} />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Question input */}
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

        <button
          className="send-button analysis-send"
          aria-label="Lancer l'analyse"
          onClick={() => void submit()}
          disabled={
            loading ||
            (files.length === 0 && !question.trim())
          }
        >
          <ArrowUp size={17} />
        </button>
      </div>

      {/* File picker */}
      <div className="analysis-file-row">
        <button
          type="button"
          className="icon-button"
          onClick={() => inputRef.current?.click()}
          aria-label="Importer des fichiers"
          title="Importer plusieurs fichiers"
          disabled={loading}
        >
          <Paperclip size={17} />
        </button>

        <input
          ref={inputRef}
          type="file"
          accept=".csv,.xlsx"
          multiple
          hidden
          onChange={(event) => chooseFiles(event.target.files)}
        />

        <span className="file-hint">
          {loading
            ? 'Import en cours...'
            : 'Ajouter des fichiers CSV ou Excel'}
        </span>
      </div>

      {error && (
        <div className="error-banner">
          {error}
        </div>
      )}
    </section>
  )
}