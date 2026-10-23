import { FileImage, FileSpreadsheet, FileText, MessageSquare, MoreHorizontal, Pencil, Star, Trash2 } from 'lucide-react'
import { memo, useEffect, useRef, useState } from 'react'
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
function HistoryItemView({ item, active, query = '', editing = false, onClick, onStartRename, onRename, onCancelRename, onToggleFavorite, onRemove }: Props) {
	const [title, setTitle] = useState(item.title ?? item.question)
	const [menuOpen, setMenuOpen] = useState(false)
	const [confirmDelete, setConfirmDelete] = useState(false)
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
		if (!nextTitle || nextTitle.length > 120) {
			inputRef.current?.setCustomValidity('Le titre doit contenir entre 1 et 120 caractères.')
			inputRef.current?.reportValidity()
			return
		}
		if (nextTitle !== (item.title ?? item.question)) void onRename?.(nextTitle)
		onCancelRename?.()
	}
	const highlightedTitle = item.title ?? item.question
	const queryIndex = query ? highlightedTitle.toLocaleLowerCase().indexOf(query.toLocaleLowerCase()) : -1
	const formattedDate = Number.isFinite(Date.parse(item.date))
		? new Date(item.date).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' })
		: item.date
	const fullTitle = item.title ?? item.question

	return (
		<div role="option" aria-selected={Boolean(active)} tabIndex={0} title={`${fullTitle}\n${formattedDate}`} className={`history-item-wrap ${active ? 'history-item-active' : ''}`} onKeyDown={(event) => {
			if (event.key === 'F2') { event.preventDefault(); onStartRename?.() }
			if (event.key === 'Delete') { event.preventDefault(); setMenuOpen(true); setConfirmDelete(true) }
			if (event.key === 'Enter') { event.preventDefault(); onClick() }
			if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
				event.preventDefault()
				const options = Array.from(event.currentTarget.parentElement?.querySelectorAll<HTMLElement>('[role="option"]') ?? [])
				const currentIndex = options.indexOf(event.currentTarget)
				options[currentIndex + (event.key === 'ArrowDown' ? 1 : -1)]?.focus()
			}
		}}>
			<div className="history-item" onClick={editing ? undefined : onClick}>
			<span className="history-file-icon"><Icon size={15} /></span>
			{editing ? (
					<input
						ref={inputRef}
						aria-label="Nouveau titre"
						value={title}
						maxLength={120}
						onChange={(event) => {
							event.currentTarget.setCustomValidity('')
							setTitle(event.target.value)
						}}
						onClick={(event) => event.stopPropagation()}
						onBlur={saveTitle}
						onKeyDown={(event) => {
							event.stopPropagation()
							if (event.key === 'Enter') { event.preventDefault(); saveTitle() }
							if (event.key === 'Escape') { event.preventDefault(); onCancelRename?.() }
						}}
					/>
				) : <button type="button" className="history-item-title" onClick={onClick}>
					<strong>{query && queryIndex >= 0
						? <>{highlightedTitle.slice(0, queryIndex)}<mark>{highlightedTitle.slice(queryIndex, queryIndex + query.length)}</mark>{highlightedTitle.slice(queryIndex + query.length)}</>
						: item.kind === 'discussion' ? highlightedTitle : item.file}</strong>
				</button>}
			{!editing && (onToggleFavorite || onRemove) && <span className="history-item-actions">
				{onToggleFavorite && item.kind === 'discussion' && <button type="button" aria-label={item.isFavorite ? 'Retirer des favoris' : 'Ajouter aux favoris'} aria-pressed={item.isFavorite} onClick={() => void onToggleFavorite()}><Star size={14} fill={item.isFavorite ? 'currentColor' : 'none'} /></button>}
				<button type="button" aria-label={`Actions pour ${fullTitle}`} aria-expanded={menuOpen} onClick={() => setMenuOpen((open) => !open)}><MoreHorizontal size={16} /></button>
				{menuOpen && <span className="history-item-menu" role="menu">
					{item.kind === 'discussion' && <button type="button" role="menuitem" onClick={() => { setMenuOpen(false); onStartRename?.() }}><Pencil size={13} /> Renommer</button>}
					{onToggleFavorite && item.kind === 'discussion' && <button type="button" role="menuitem" onClick={() => { setMenuOpen(false); void onToggleFavorite() }}><Star size={13} /> {item.isFavorite ? 'Retirer des favoris' : 'Ajouter aux favoris'}</button>}
					{onRemove && !confirmDelete && <button type="button" role="menuitem" onClick={() => setConfirmDelete(true)}><Trash2 size={13} /> Supprimer</button>}
					{onRemove && confirmDelete && <span className="history-delete-confirm" role="group" aria-label="Confirmer la suppression">
						<span>Supprimer ?</span>
						<button type="button" onClick={() => { setMenuOpen(false); setConfirmDelete(false); void onRemove() }}>Confirmer</button>
						<button type="button" onClick={() => setConfirmDelete(false)}>Annuler</button>
					</span>}
				</span>}
			</span>}
		</div>
		</div>
	)
}

export const HistoryItem = memo(HistoryItemView)