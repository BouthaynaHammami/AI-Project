import { ArrowUp, CheckCircle2, FileUp, Paperclip } from 'lucide-react'
import { useRef, useState } from 'react'

type Props = { onAnalyze: (file: File | null, question: string) => void }

export function AnalysisBar({ onAnalyze }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [question, setQuestion] = useState('')
  const [error, setError] = useState('')
  const chooseFile = (candidate?: File) => {
    if (!candidate) return
    if (!/\.(csv|xlsx)$/i.test(candidate.name)) { setError('Utilisez uniquement un fichier .csv ou .xlsx.'); setFile(null); return }
    setError(''); setFile(candidate)
  }
  const submit = () => { if (file || question.trim()) onAnalyze(file, question.trim()) }
  return <section className="analysis-bar"><div className="analysis-bar-top"><span className="section-kicker">NOUVELLE ANALYSE</span><span className="analysis-bar-hint">Posez une question sur vos données</span></div><div className="analysis-chat-row"><input className="question-input" value={question} onChange={(event) => setQuestion(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') submit() }} placeholder="Posez une question sur vos données..." /><button className="send-button analysis-send" aria-label="Lancer l'analyse" onClick={submit} disabled={!file && !question.trim()}><ArrowUp size={17} /></button></div><div className="analysis-file-row"><button className="icon-button" onClick={() => inputRef.current?.click()} aria-label="Importer un fichier" title="Importer un fichier"><Paperclip size={17} /></button><input ref={inputRef} type="file" accept=".csv,.xlsx" hidden onChange={(event) => chooseFile(event.target.files?.[0])} /><span className="file-hint">Ajouter un fichier CSV ou Excel</span>{file && <span className="selected-file"><FileUp size={15} /> {file.name} <CheckCircle2 size={14} /></span>}</div>{error && <div className="error-banner">{error}</div>}</section>
}