import type { HistoryEntry } from '../types'
import { HistoryItem } from './HistoryItem'

type Props = {
  title: string
  items: HistoryEntry[]
  activeId: number
  query: string
  editingId: number | null
  onHistory: (id: number) => void
  onStartRename: (id: number) => void
  onRename: (item: HistoryEntry, title: string) => Promise<void>
  onCancelRename: () => void
  onToggleFavorite: (item: HistoryEntry) => Promise<void>
  onRemove: (item: HistoryEntry) => Promise<void>
  sentinelRef?: (node: HTMLDivElement | null) => void
}

export function HistoryGroup(props: Props) {
  if (!props.items.length) return null
  return (
    <section className="history-group" aria-label={props.title}>
      <h3>{props.title}</h3>
      <div role="listbox" aria-label={props.title}>
        {props.items.map((item) => (
          <HistoryItem
            key={`${item.kind}-${item.id}`}
            item={item}
            active={props.activeId === item.id}
            query={props.query}
            editing={props.editingId === item.id}
            onClick={() => props.onHistory(item.id)}
            onStartRename={() => props.onStartRename(item.id)}
            onRename={(title) => props.onRename(item, title)}
            onCancelRename={props.onCancelRename}
            onToggleFavorite={() => props.onToggleFavorite(item)}
            onRemove={() => props.onRemove(item)}
          />
        ))}
      </div>
      {props.sentinelRef && <div ref={props.sentinelRef} className="history-pagination-sentinel" aria-hidden="true" />}
    </section>
  )
}
