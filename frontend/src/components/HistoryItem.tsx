import { FileImage, FileSpreadsheet, FileText, MessageSquare, Star, Trash2 } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { HistoryEntry } from '../types'

type Props = {
	item: HistoryEntry
	active?: boolean
	query?: string
	editing?: boolean
	onClick: () => void
	onStartRename?: () => void
	onRename?: (title: string) => Promise<void>
	onCancelRename?: () => void
	onToggleFavorite?: () => Promise<void>
	onRemove?: () => Promise<void>
}
export function HistoryItem({ item, active, query = '', editing = false, onClick, onStartRename, onRename, onCancelRename, onToggleFavorite, onRemove }: Props) {
	const [title, setTitle] = useState(item.title ?? item.question)
	const inputRef = useRef<HTMLInputElement>(null)
	const extension = item.file.split('.').pop()?.toLowerCase()
	const Icon = item.kind === 'discussion'
		? MessageSquare
		: extension === 'pdf' || extension === 'doc' || extension === 'docx'
			? FileText
			: extension === 'png' || extension === 'jpg' || extension === 'jpeg'
				? FileImage
				: FileSpreadsheet

	useEffect(() => {
		if (editing) {
			setTitle(item.title ?? item.question)
			inputRef.current?.focus()
			inputRef.current?.select()
		}
	}, [editing, item.question, item.title])

	const saveTitle = () => {
		const nextTitle = title.trim()
		if (nextTitle && nextTitle !== (item.title ?? item.question)) void onRename?.(nextTitle)
		onCancelRename?.()
	}
	const highlightedTitle = item.title ?? item.question
	const queryIndex = query ? highlightedTitle.toLocaleLowerCase().indexOf(query.toLocaleLowerCase()) : -1
	const formattedDate = Number.isFinite(Date.parse(item.date))
		? new Date(item.date).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' })
		: item.date

	return (
		<div role="option" aria-selected={Boolean(active)} tabIndex={0} className={`history-item-wrap ${active ? 'history-item-active' : ''}`} onKeyDown={(event) => {
			if (event.key === 'F2') { event.preventDefault(); onStartRename?.() }
			if (event.key === 'Delete') { event.preventDefault(); void onRemove?.() }
		}}>
			<button type="button" className={`history-item ${active ? 'history-item-active' : ''}`} onClick={onClick}>
			<span className="history-file-icon"><Icon size={15} /></span>
			<span className="min-w-0 text-left">
				<strong>{editing ? (
					<input
						ref={inputRef}
						aria-label="Nouveau titre"
						value={title}
						onChange={(event) => setTitle(event.target.value)}
						onClick={(event) => event.stopPropagation()}
						onKeyDown={(event) => {
							event.stopPropagation()
							if (event.key === 'Enter') saveTitle()
							if (event.key === 'Escape') onCancelRename?.()
						}}
					/>
				) : item.kind === 'discussion' && query && queryIndex >= 0 ? (
					<>Discussion · {highlightedTitle.slice(0, queryIndex)}<mark>{highlightedTitle.slice(queryIndex, queryIndex + query.length)}</mark>{highlightedTitle.slice(queryIndex + query.length)}</>
				) : item.kind === 'discussion' ? highlightedTitle : item.file}</strong>
				<small>{formattedDate}</small>
			</span>
			</button>
			{!editing && (onToggleFavorite || onRemove) && <span className="history-item-actions">
				{onToggleFavorite && <button type="button" aria-label={item.isFavorite ? 'Retirer des favoris' : 'Ajouter aux favoris'} onClick={() => void onToggleFavorite()}><Star size={14} fill={item.isFavorite ? 'currentColor' : 'none'} /></button>}
				{onRemove && <button type="button" aria-label="Supprimer de l’historique" onClick={() => void onRemove()}><Trash2 size={14} /></button>}
			</span>}
		</div>
	)
}