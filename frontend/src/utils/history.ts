import type { HistoryEntry } from '../types'

export type HistoryGroups = {
  today: HistoryEntry[]
  yesterday: HistoryEntry[]
  thisWeek: HistoryEntry[]
  older: HistoryEntry[]
}

function localDay(value: Date): number {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate()).getTime()
}

export function groupByDate(items: HistoryEntry[], now = new Date()): HistoryGroups {
  const today = localDay(now)
  const yesterday = today - 24 * 60 * 60 * 1000
  const weekStart = today - 6 * 24 * 60 * 60 * 1000
  const groups: HistoryGroups = { today: [], yesterday: [], thisWeek: [], older: [] }

  for (const item of items) {
    const timestamp = Date.parse(item.date)
    if (!Number.isFinite(timestamp)) {
      groups.older.push(item)
      continue
    }
    const date = localDay(new Date(timestamp))
    if (date === today) groups.today.push(item)
    else if (date === yesterday) groups.yesterday.push(item)
    else if (date >= weekStart) groups.thisWeek.push(item)
    else groups.older.push(item)
  }

  return groups
}
