// Friendly names for unsupported document types
const UNSUPPORTED_DOC_NAMES: Record<string, string> = {
  'contract': 'general contracts (try uploading a specific contract type)',
  'unknown': 'this type of document',
}

interface UnsupportedModalProps {
  show: boolean
  unsupportedType: string
  waitlistEmail: string
  emailSubmitted: boolean
  onEmailChange: (value: string) => void
  onSubmit: () => void
  onClose: () => void
  onReset: () => void
}

export default function UnsupportedModal({ show, unsupportedType, waitlistEmail, emailSubmitted, onEmailChange, onSubmit, onClose, onReset }: UnsupportedModalProps) {
  if (!show) return null

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <span className="modal-icon">[!]</span>
          <h2>COMING SOON</h2>
        </div>
        <div className="modal-content">
          {emailSubmitted ? (
            <>
              <p className="modal-success">GOT IT!</p>
              <p>We'll ping you at <strong>{waitlistEmail}</strong> when we add support for {UNSUPPORTED_DOC_NAMES[unsupportedType] || unsupportedType}.</p>
              <button className="pixel-btn primary" onClick={onReset}>
                [OK] COOL
              </button>
            </>
          ) : (
            <>
              <p>Sorry... we haven't done our homework on <strong>{UNSUPPORTED_DOC_NAMES[unsupportedType] || unsupportedType}</strong>.</p>
              <p>Yet.</p>
              <p className="modal-cta">Drop your email and we'll ping you first thing:</p>
              <input
                type="email"
                className="pixel-input"
                placeholder="you@example.com"
                value={waitlistEmail}
                onChange={(e) => onEmailChange(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && waitlistEmail && onSubmit()}
              />
              <div className="modal-buttons">
                <button
                  className="pixel-btn primary"
                  onClick={onSubmit}
                  disabled={!waitlistEmail}
                >
                  [NOTIFY ME]
                </button>
                <button className="pixel-btn secondary" onClick={onClose}>
                  [NEVERMIND]
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
