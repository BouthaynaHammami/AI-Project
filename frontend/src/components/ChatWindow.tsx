import { ArrowDownUp, Bot, Check, Copy, LoaderCircle, MessageCircle, Paperclip, Send, ThumbsDown, ThumbsUp, UserRound } from 'lucide-react'
import { useRef, useState, type ChangeEvent } from 'react'
import { getApiError } from '../services/api'
import type { ChartConfig, Message } from '../types'
import { ChartRenderer } from './ChartRenderer'

type Props = {
  messages: Message[]
  isAnalyzing: boolean
  onAsk: (question: string) => void
  onFeedback: (analysisId: number, rating: 1 | -1, comment: string | null) => Promise<void>
  onClearFeedback: (analysisId: number) => Promise<void>
  onNewConversation: () => void
  onAddFiles: (files: File[]) => Promise<void>
}

type ParsedTable = {
  headers: string[]
  rows: string[][]
  before: string
  after: string
}

const splitTableRow = (line: string) =>
  line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map((cell) => cell.trim())

function parseMarkdownTable(content: string): ParsedTable | null {
  const lines = content.split(/\r?\n/)
  for (let index = 1; index < lines.length; index += 1) {
    const divider = splitTableRow(lines[index])
    if (divider.length < 2 || !divider.every((cell) => /^:?-{3,}:?$/.test(cell))) continue
    if (!lines[index - 1].includes('|')) continue

    const headers = splitTableRow(lines[index - 1])
    const rows: string[][] = []
    let end = index + 1
    while (end < lines.length && lines[end].includes('|')) {
      rows.push(splitTableRow(lines[end]))
      end += 1
    }
    return {
      headers,
      rows,
      before: lines.slice(0, index - 1).join('\n').trim(),
      after: lines.slice(end).join('\n').trim(),
    }
  }
  return null
}

function AnswerText({ content }: { content: string }) {
  const lines = content.split(/\r?\n/)
  return (
    <div className="answer-text">
      {lines.map((line, index) => {
        if (!line.trim()) return <div className="answer-line-spacer" key={index} />
        const isListItem = /^\s*(?:[-*•]|\d+[.)])\s+/.test(line)
        const text = line.replace(/^\s*(?:[-*•]|\d+[.)])\s+/, '')
        const fragments = text.split(/(\*\*[^*]+\*\*|\b\d+(?:[.,]\d+)?(?:\s?(?:%|€|\$))?)/g)
        const formatted = fragments.map((fragment, fragmentIndex) => {
          if (fragment.startsWith('**') && fragment.endsWith('**')) {
            return <strong key={fragmentIndex}>{fragment.slice(2, -2)}</strong>
          }
          if (/^\d/.test(fragment)) {
            return <strong className="answer-highlight" key={fragmentIndex}>{fragment}</strong>
          }
          return <span key={fragmentIndex}>{fragment}</span>
        })
        return isListItem
          ? <div className="answer-list-item" key={index}><span aria-hidden="true">•</span><div>{formatted}</div></div>
          : <p key={index}>{formatted}</p>
      })}
    </div>
  )
}

function AssistantResponse({ message, onAsk, onFeedback, onClearFeedback }: { message: Message; onAsk: (question: string) => void; onFeedback: Props['onFeedback']; onClearFeedback: Props['onClearFeedback'] }) {
  const [sort, setSort] = useState<{ column: number; direction: 'asc' | 'desc' } | null>(null)
  const [copied, setCopied] = useState(false)
  const [codeCopied, setCodeCopied] = useState(false)
  const [feedbackError, setFeedbackError] = useState('')
  const table = parseMarkdownTable(message.content)
  let chart: ChartConfig | null = null
  try {
    chart = message.chartConfig ? JSON.parse(message.chartConfig) as ChartConfig : null
  } catch {
    chart = null
  }
  const rows = table ? [...table.rows] : []

  if (table && sort) {
    rows.sort((left, right) => {
      const a = left[sort.column] ?? ''
      const b = right[sort.column] ?? ''
      const aNumber = Number(a.replace(/[\s,%€$]/g, '').replace(',', '.'))
      const bNumber = Number(b.replace(/[\s,%€$]/g, '').replace(',', '.'))
      const comparison = Number.isFinite(aNumber) && Number.isFinite(bNumber)
        ? aNumber - bNumber
        : a.localeCompare(b, 'fr', { numeric: true, sensitivity: 'base' })
      return sort.direction === 'asc' ? comparison : -comparison
    })
  }

  const copyAnswer = async () => {
    try {
      await navigator.clipboard.writeText(message.content)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1800)
    } catch {
      setCopied(false)
    }
  }

  const copyGeneratedCode = async () => {
    if (!message.generatedCode) return
    try {
      await navigator.clipboard.writeText(message.generatedCode)
      setCodeCopied(true)
      window.setTimeout(() => setCodeCopied(false), 1800)
    } catch {
      setCodeCopied(false)
    }
  }

  const askFollowUp = () => {
    const excerpt = message.content.replace(/\s+/g, ' ').slice(0, 350)
    onAsk(`Peux-tu approfondir ce résultat et expliquer les chiffres qui le justifient ? Réponse précédente : ${excerpt}`)
  }

  const rateAnswer = async (rating: 1 | -1, comment: string | null = null) => {
    if (!message.analysisId) return
    setFeedbackError('')
    try {
      await onFeedback(message.analysisId, rating, comment)
    } catch {
      setFeedbackError('Le vote n’a pas pu être enregistré. Réessayez.')
    }
  }

  const clearAnswerFeedback = async () => {
    if (!message.analysisId) return
    setFeedbackError('')
    try {
      await onClearFeedback(message.analysisId)
    } catch {
      setFeedbackError('Le vote n’a pas pu être annulé. Réessayez.')
    }
  }

  return (
    <div className="assistant-response">
      {table ? (
        <>
          {table.before && <AnswerText content={table.before} />}
          <div className="answer-table-scroll">
            <table className="answer-table">
              <thead>
                <tr>
                  {table.headers.map((header, index) => (
                    <th key={`${header}-${index}`} aria-sort={sort?.column === index ? (sort.direction === 'asc' ? 'ascending' : 'descending') : 'none'}>
                      <button type="button" onClick={() => setSort((current) => ({ column: index, direction: current?.column === index && current.direction === 'asc' ? 'desc' : 'asc' }))}>
                        {header}<ArrowDownUp size={13} />
                      </button>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row, rowIndex) => (
                  <tr key={rowIndex}>{table.headers.map((_, columnIndex) => <td key={columnIndex}>{row[columnIndex] ?? ''}</td>)}</tr>
                ))}
              </tbody>
            </table>
          </div>
          {table.after && <AnswerText content={table.after} />}
        </>
      ) : (
        <AnswerText content={message.content} />
      )}
      {chart && <ChartRenderer config={chart} />}
      <div className="answer-actions">
        <button type="button" onClick={() => void copyAnswer()} title="Copier la réponse">
          {copied ? <Check size={14} /> : <Copy size={14} />}
          {copied ? 'Copié' : 'Copier'}
        </button>
        <button type="button" onClick={askFollowUp} title="Poser une question de suivi">
          <MessageCircle size={14} />
          Question de suivi
        </button>
        {message.analysisId && (
          <div className="answer-feedback" aria-label="Évaluer cette réponse">
            <button
              type="button"
              className={message.feedback?.rating === 1 ? 'answer-feedback-selected' : ''}
              onClick={() => void (message.feedback?.rating === 1 ? clearAnswerFeedback() : rateAnswer(1))}
              aria-label={message.feedback?.rating === 1 ? 'Annuler le vote positif' : 'Réponse utile'}
              aria-pressed={message.feedback?.rating === 1}
              title={message.feedback?.rating === 1 ? 'Annuler le vote' : 'Réponse utile'}
            >
              <ThumbsUp size={15} strokeWidth={1.7} />
            </button>
            <button
              type="button"
              className={message.feedback?.rating === -1 ? 'answer-feedback-selected' : ''}
              onClick={() => void (message.feedback?.rating === -1 ? clearAnswerFeedback() : rateAnswer(-1, null))}
              aria-label={message.feedback?.rating === -1 ? 'Annuler le vote négatif' : 'Réponse pas utile'}
              aria-pressed={message.feedback?.rating === -1}
              title={message.feedback?.rating === -1 ? 'Annuler le vote' : 'Réponse pas utile'}
            >
              <ThumbsDown size={15} strokeWidth={1.7} />
            </button>
          </div>
        )}
      </div>
      {message.analysisId && message.feedback?.rating === -1 && (
        <label className="answer-feedback-reason">
          <span>Que s’est-il passé ?</span>
          <select
            value={message.feedback.comment ?? ''}
            onChange={(event) => void rateAnswer(-1, event.target.value || null)}
          >
            <option value="">Choisir une raison (facultatif)</option>
            <option value="Mauvais chiffre">Mauvais chiffre</option>
            <option value="Graphique inutile">Graphique inutile</option>
            <option value="Ne répond pas à la question">Ne répond pas à la question</option>
            <option value="Autre">Autre</option>
          </select>
        </label>
      )}
      {feedbackError && <p className="answer-feedback-error" role="alert">{feedbackError}</p>}
      {message.generatedCode && (
        <details className="generated-code-details">
          <summary>Voir le code généré</summary>
          <div className="generated-code-toolbar">
            {message.codeRetried && <span className="generated-code-corrected">Corrigé automatiquement</span>}
            <button type="button" onClick={() => void copyGeneratedCode()}>
              {codeCopied ? <Check size={13} /> : <Copy size={13} />}
              {codeCopied ? 'Copié' : 'Copier'}
            </button>
          </div>
          <pre className="generated-code-block"><code>{message.generatedCode}</code></pre>
          {message.codeExplanation && <p className="generated-code-explanation">{message.codeExplanation}</p>}
        </details>
      )}
    </div>
  )
}

export function ChatWindow({ messages, isAnalyzing, onAsk, onFeedback, onClearFeedback, onNewConversation, onAddFiles }: Props) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [question, setQuestion] = useState('')
  const [addingFiles, setAddingFiles] = useState(false)
  const [fileError, setFileError] = useState('')

  const submit = () => {
    if (!question.trim() || isAnalyzing) return
    onAsk(question.trim())
    setQuestion('')
  }

  const handleFiles = async (event: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.currentTarget.files ?? [])
    event.currentTarget.value = ''
    if (!files.length) return

    setAddingFiles(true)
    setFileError('')
    try {
      await onAddFiles(files)
    } catch (error) {
      setFileError(getApiError(error))
    } finally {
      setAddingFiles(false)
    }
  }

  return (
    <section className="chat-section">
      <div className="chat-heading">
        <div>
          <span className="section-kicker">ÉTAPE 02</span>
          <h2>Posez votre question</h2>
        </div>
        <div className="chat-heading-actions">
          <button type="button" className="new-conversation-button" onClick={onNewConversation} disabled={isAnalyzing}>
            Nouvelle conversation
          </button>
          <span className="online-dot">IA en ligne</span>
        </div>
      </div>
      <div className="messages" role="log" aria-live="polite">
        {messages.map((message) => (
          <div className={`message-row ${message.role === 'user' ? 'message-user' : ''}`} key={message.id}>
            <span className={`avatar ${message.role === 'user' ? 'avatar-user' : 'avatar-ai'}`}>
              {message.role === 'user' ? <UserRound size={15} /> : <Bot size={17} />}
            </span>
            <div className="message-content">
              {message.role === 'assistant'
                ? <AssistantResponse message={message} onAsk={onAsk} onFeedback={onFeedback} onClearFeedback={onClearFeedback} />
                : <p className="font-chat">{message.content}</p>}
              <time>{message.timestamp}</time>
            </div>
          </div>
        ))}
        {isAnalyzing && (
          <div className="message-row analysis-loading-row" role="status" aria-label="Analyse en cours">
            <span className="avatar avatar-ai"><LoaderCircle className="analysis-spinner" size={17} /></span>
            <div className="analysis-skeleton">
              <span />
              <span />
              <span />
            </div>
          </div>
        )}
      </div>
      <div className="prompt-box">
        <button
          type="button"
          className="icon-button chat-import-button"
          onClick={() => fileInputRef.current?.click()}
          disabled={addingFiles || isAnalyzing}
          aria-label="Importer un fichier dans cette analyse"
          title="Importer CSV ou Excel dans cette analyse"
        >
          <Paperclip size={17} />
        </button>
        <input ref={fileInputRef} type="file" accept=".csv,.xls,.xlsx" multiple hidden onChange={(event) => void handleFiles(event)} />
        <textarea
          value={question}
          disabled={isAnalyzing}
          onChange={(event) => setQuestion(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault()
              submit()
            }
          }}
          placeholder={addingFiles ? 'Import du fichier en cours...' : 'Ex : Compare les performances par groupe...'}
          rows={1}
        />
        <button className="send-button" aria-label="Analyser" onClick={submit} disabled={isAnalyzing || !question.trim()}>
          <Send size={17} />
        </button>
      </div>
      {fileError && <div className="error-banner">{fileError}</div>}
      <p className="prompt-hint">Appuyez sur Entrée pour envoyer · Les analyses sont générées à partir de vos données</p>
    </section>
  )
}