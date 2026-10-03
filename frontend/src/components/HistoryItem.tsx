import { FileImage, FileSpreadsheet, FileText, MessageSquare } from 'lucide-react'
import type { HistoryEntry } from '../types'

type Props = { item: HistoryEntry; active?: boolean; onClick: () => void }
export function HistoryItem({ item, active, onClick }: Props) {
	const extension = item.file.split('.').pop()?.toLowerCase()
	const Icon = item.kind === 'discussion'
		? MessageSquare
		: extension === 'pdf' || extension === 'doc' || extension === 'docx'
			? FileText
			: extension === 'png' || extension === 'jpg' || extension === 'jpeg'
				? FileImage
				: FileSpreadsheet

	return (
		<button className={`history-item ${active ? 'history-item-active' : ''}`} onClick={onClick}>
			<span className="history-file-icon"><Icon size={15} /></span>
			<span className="min-w-0 text-left">
				<strong>{item.kind === 'discussion' ? `Discussion · ${item.file}` : item.file}</strong>
				<span>{item.kind === 'discussion' ? item.question : 'Import du fichier'}</span>
				<small>{item.date}</small>
			</span>
		</button>
	)
}