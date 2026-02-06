interface DisclaimerModalProps {
  show: boolean
  disclaimerInput: string
  onInputChange: (value: string) => void
  onSubmit: () => void
  onCancel: () => void
}

export default function DisclaimerModal({ show, disclaimerInput, onInputChange, onSubmit, onCancel }: DisclaimerModalProps) {
  if (!show) return null

  return (
    <div className="modal-overlay">
      <div className="modal disclaimer-modal">
        <div className="modal-header">
          <span className="modal-icon">[!]</span>
          <h2>HOLD UP</h2>
        </div>
        <div className="modal-content">
          <p>Hey! I'm trying my best here but <strong>I'm not a lawyer</strong> and neither is Claude!</p>
          <p>This tool is for <strong>educational purposes only</strong>. It might miss things. It might be wrong. If you need a lawyer, get a lawyer dawg.</p>
          <p className="modal-cta">Type <strong>"not legal advice"</strong> to confirm you understand:</p>
          <input
            type="text"
            className="pixel-input"
            placeholder="not legal advice"
            value={disclaimerInput}
            onChange={(e) => onInputChange(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && onSubmit()}
            autoFocus
          />
          <div className="modal-buttons">
            <button
              className="pixel-btn primary"
              onClick={onSubmit}
              disabled={disclaimerInput.toLowerCase().trim() !== 'not legal advice'}
            >
              [GOT IT]
            </button>
            <button className="pixel-btn secondary" onClick={onCancel}>
              [BACK]
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
