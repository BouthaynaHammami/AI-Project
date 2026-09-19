import { FileSpreadsheet } from 'lucide-react'
import type { HistoryEntry } from '../types'

type Props = { item: HistoryEntry; active?: boolean; onClick: () => void }
export function HistoryItem({ item, active, onClick }: Props) { return <button className={`history-item ${active ? 'history-item-active' : ''}`} onClick={onClick}><span className="history-file-icon"><FileSpreadsheet size={15} /></span><span className="min-w-0 text-left"><strong>{item.file}</strong><span>{item.question}</span><small>{item.date}</small></span></button> }