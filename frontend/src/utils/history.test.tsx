import { act, cleanup, fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { HistoryItem } from '../components/HistoryItem'
import { Sidebar } from '../components/Sidebar'
import { useDemoData } from '../hooks/useDemoData'
import type { HistoryEntry } from '../types'
import { groupByDate } from './history'

const item = (id: number, date: Date): HistoryEntry => ({
  id,
  kind: 'discussion',
  file: 'ventes.csv',
  datasetId: 2,
  datasetIds: [2],
  question: `Question ${id}`,
  answer: 'Réponse',
  chartConfig: null,
  generatedCode: null,
  codeExplanation: null,
  codeRetried: false,
  feedback: null,
  conversationId: id,
  conversationTitle: null,
  date: date.toISOString(),
  analysisId: id,
  title: `Question ${id}`,
  isFavorite: false,
})

const sampleConversation = vi.hoisted(() => ({
  id: 24,
  title: 'Quelle région a le plus de ventes ?',
  dataset_ids: [2],
  is_favorite: false,
  created_at: '2026-10-04T10:00:00Z',
  updated_at: '2026-10-04T10:00:00Z',
}))
const getConversationMock = vi.hoisted(() => vi.fn().mockResolvedValue({ ...sampleConversation, messages: [] }))
const datasetHistoryMock = vi.hoisted(() => vi.fn().mockResolvedValue([]))
const conversationStore = vi.hoisted(() => ({
  items: [] as Array<{
    id: number
    title: string
    dataset_ids: number[]
    is_favorite: boolean
    created_at: string
    updated_at: string
  }>,
}))
conversationStore.items = [sampleConversation]

vi.mock('../services/analysisService', () => ({
  addConversationMessage: vi.fn(),
  createConversation: vi.fn().mockResolvedValue(sampleConversation),
  deleteConversation: vi.fn().mockImplementation(async (id: number) => {
    conversationStore.items = conversationStore.items.filter((conversation) => conversation.id !== id)
  }),
  deleteAnalysis: vi.fn().mockResolvedValue(undefined),
  getConversation: getConversationMock,
  getConversations: vi.fn().mockImplementation(async () => conversationStore.items),
  restoreAnalysis: vi.fn().mockResolvedValue(undefined),
  updateConversation: vi.fn().mockResolvedValue(sampleConversation),
}))

vi.mock('../services/fileService', () => ({
  deleteDataset: vi.fn().mockResolvedValue(undefined),
  getDatasetHistory: datasetHistoryMock,
  getDatasetPreview: vi.fn(),
}))

afterEach(() => {
  cleanup()
  vi.useRealTimers()
  vi.clearAllMocks()
  getConversationMock.mockResolvedValue({ ...sampleConversation, messages: [] })
  datasetHistoryMock.mockResolvedValue([])
  conversationStore.items = [sampleConversation]
})

describe('groupByDate', () => {
  it('groups local midnight, yesterday and the exact seven-day boundary', () => {
    const now = new Date(2026, 9, 7, 0, 15)
    const groups = groupByDate([
      item(1, new Date(2026, 9, 7, 0, 0)),
      item(2, new Date(2026, 9, 6, 23, 59)),
      item(3, new Date(2026, 9, 1, 12, 0)),
      item(4, new Date(2026, 8, 30, 12, 0)),
    ], now)

    expect(groups.today.map((entry) => entry.id)).toEqual([1])
    expect(groups.yesterday.map((entry) => entry.id)).toEqual([2])
    expect(groups.thisWeek.map((entry) => entry.id)).toEqual([3])
    expect(groups.older.map((entry) => entry.id)).toEqual([4])
  })
})

describe('history interactions', () => {
  it('restores generated code and explanation from conversation history', async () => {
    getConversationMock.mockResolvedValueOnce({
      ...sampleConversation,
      messages: [
        { id: 1, role: 'user', content: 'Total ?', created_at: '2026-10-04T10:00:00Z' },
        {
          id: 2,
          role: 'assistant',
          content: 'Le total est 42.',
          result_data: {
            generated_code: "print(df['amount'].sum())",
            code_explanation: 'Le code additionne les montants.',
            code_retried: true,
          },
          created_at: '2026-10-04T10:00:01Z',
        },
      ],
    })
    const { result } = renderHook(() => useDemoData())

    await act(async () => { await result.current.loadHistoryEntry(24) })

    expect(result.current.messages[1]).toMatchObject({
      generatedCode: "print(df['amount'].sum())",
      codeExplanation: 'Le code additionne les montants.',
      codeRetried: true,
    })
  })

  it('debounces rapid search input to one request', async () => {
    vi.useFakeTimers()
    const onSearch = vi.fn().mockResolvedValue(undefined)
    render(
      <Sidebar
        userName="Test"
        profilePhoto=""
        history={[]}
        activeId={0}
        query=""
        favoriteOnly={false}
        loading={false}
        hasMore={false}
        error=""
        undoEntry={null}
        cascadePrompt={null}
        onNew={vi.fn()}
        onHistory={vi.fn()}
        onSettings={vi.fn()}
        onLogout={vi.fn()}
        onSearch={onSearch}
        onLoadMore={vi.fn()}
        onRetry={vi.fn()}
        onRename={vi.fn()}
        onToggleFavorite={vi.fn()}
        onRemove={vi.fn()}
        onUndoRemove={vi.fn()}
        onConfirmCascade={vi.fn()}
        onCancelCascade={vi.fn()}
      />,
    )

    const search = screen.getByRole('textbox', { name: 'Rechercher dans l’historique' })
    fireEvent.change(search, { target: { value: 'ven' } })
    fireEvent.change(search, { target: { value: 'ventes' } })
    await act(async () => { vi.advanceTimersByTime(299) })
    expect(onSearch).not.toHaveBeenCalled()
    await act(async () => { vi.advanceTimersByTime(1) })
    expect(onSearch).toHaveBeenCalledTimes(1)
    expect(onSearch).toHaveBeenCalledWith('ventes', false)
  })

  it('renames on Enter and cancels edits on Escape', async () => {
    const onRename = vi.fn().mockResolvedValue(undefined)
    const onStartRename = vi.fn()
    const onCancelRename = vi.fn()
    const entry = item(4, new Date())
    const { rerender } = render(
      <HistoryItem
        item={entry}
        editing={false}
        onClick={vi.fn()}
        onStartRename={onStartRename}
        onRename={onRename}
        onCancelRename={onCancelRename}
        onToggleFavorite={vi.fn()}
        onRemove={vi.fn()}
      />,
    )
    const option = screen.getByRole('option')
    fireEvent.keyDown(option, { key: 'F2' })
    expect(onStartRename).toHaveBeenCalled()
    rerender(
      <HistoryItem
        item={entry}
        editing
        onClick={vi.fn()}
        onStartRename={onStartRename}
        onRename={onRename}
        onCancelRename={onCancelRename}
        onToggleFavorite={vi.fn()}
        onRemove={vi.fn()}
      />,
    )
    const input = screen.getByRole('textbox', { name: 'Nouveau titre' })
    fireEvent.change(input, { target: { value: 'Rapport octobre' } })
    fireEvent.keyDown(input, { key: 'Enter' })
    await waitFor(() => expect(onRename).toHaveBeenCalledWith('Rapport octobre'))
    expect(onCancelRename).toHaveBeenCalled()

    fireEvent.keyDown(screen.getByRole('option'), { key: 'F2' })
    rerender(
      <HistoryItem
        item={entry}
        editing
        onClick={vi.fn()}
        onStartRename={onStartRename}
        onRename={onRename}
        onCancelRename={onCancelRename}
        onToggleFavorite={vi.fn()}
        onRemove={vi.fn()}
      />,
    )
    fireEvent.change(screen.getByRole('textbox', { name: 'Nouveau titre' }), { target: { value: 'À annuler' } })
    fireEvent.keyDown(screen.getByRole('textbox', { name: 'Nouveau titre' }), { key: 'Escape' })
    expect(onRename).toHaveBeenCalledTimes(1)
    expect(onCancelRename).toHaveBeenCalledTimes(2)
  })

  it('deletes a conversation and removes it from history', async () => {
    const { result } = renderHook(() => useDemoData())
    await waitFor(() => expect(result.current.history).toHaveLength(1))
    const entry = result.current.history[0]

    await act(async () => { await result.current.remove(entry) })
    expect(result.current.history).toHaveLength(0)
    expect(entry.conversationId).toBe(24)
  })

  it('restores a pending conversation deletion when undo is clicked', async () => {
    const { result } = renderHook(() => useDemoData())
    await waitFor(() => expect(result.current.history).toHaveLength(1))
    await act(async () => { await result.current.remove(result.current.history[0]) })
    expect(result.current.history).toHaveLength(0)
    expect(result.current.undoEntry).not.toBeNull()
    await act(async () => { await result.current.undoRemove() })
    expect(result.current.history).toHaveLength(1)
    expect(result.current.undoEntry).toBeNull()
  })

  it('finalizes a pending conversation deletion after five seconds', async () => {
    vi.useFakeTimers()
    const { result } = renderHook(() => useDemoData())
    await act(async () => { await result.current.refreshHistory() })
    await act(async () => { await result.current.remove(result.current.history[0]) })
    expect(result.current.history).toHaveLength(0)
    await act(async () => { vi.advanceTimersByTime(5000) })
    expect(result.current.undoEntry).toBeNull()
    expect(result.current.history).toHaveLength(0)
    const { deleteConversation } = await import('../services/analysisService')
    expect(deleteConversation).toHaveBeenCalledWith(24)
  })

  it('delays dataset deletion for five seconds and cancels it on undo', async () => {
    vi.useFakeTimers()
    datasetHistoryMock.mockResolvedValue([
      { id: 52, filename: 'ventes.csv', created_at: '2026-10-04T10:00:00Z' },
    ])
    const { result } = renderHook(() => useDemoData())
    await act(async () => { await result.current.refreshHistory() })
    const dataset = result.current.history.find((entry) => entry.kind === 'import')
    expect(dataset).toBeDefined()
    await act(async () => { await result.current.remove(dataset!) })
    expect(result.current.history.some((entry) => entry.kind === 'import')).toBe(false)
    await act(async () => { await result.current.undoRemove() })
    await act(async () => { vi.advanceTimersByTime(5000) })
    const { deleteDataset } = await import('../services/fileService')
    expect(deleteDataset).not.toHaveBeenCalled()
    expect(result.current.history.some((entry) => entry.kind === 'import')).toBe(true)
  })
})
