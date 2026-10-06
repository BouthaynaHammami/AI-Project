type Props = { message: string; onUndo: () => void }

export function UndoToast({ message, onUndo }: Props) {
  return (
    <div className="history-undo-toast" role="status" aria-live="polite">
      <span>{message}</span>
      <button onClick={onUndo}>Annuler</button>
    </div>
  )
}
