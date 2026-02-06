interface AuthModalProps {
  show: boolean
  authMode: 'login' | 'signup'
  authEmail: string
  authPassword: string
  authError: string | null
  authLoading: boolean
  onEmailChange: (value: string) => void
  onPasswordChange: (value: string) => void
  onLogin: () => void
  onSignup: () => void
  onClose: () => void
  onSwitchMode: (mode: 'login' | 'signup') => void
}

export default function AuthModal({ show, authMode, authEmail, authPassword, authError, authLoading, onEmailChange, onPasswordChange, onLogin, onSignup, onClose, onSwitchMode }: AuthModalProps) {
  if (!show) return null

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal auth-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <span className="modal-icon">[*]</span>
          <h2>{authMode === 'login' ? 'LOG IN' : 'SIGN UP'}</h2>
        </div>
        <div className="modal-content">
          <p className="auth-benefit">
            Sign in to save your analysis history and access it anytime.
          </p>

          {authError && (
            <div className="auth-error">{authError}</div>
          )}

          <input
            type="email"
            className="pixel-input"
            placeholder="Email"
            value={authEmail}
            onChange={(e) => onEmailChange(e.target.value)}
            disabled={authLoading}
          />
          <input
            type="password"
            className="pixel-input"
            placeholder="Password"
            value={authPassword}
            onChange={(e) => onPasswordChange(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && (authMode === 'login' ? onLogin() : onSignup())}
            disabled={authLoading}
          />

          <div className="modal-buttons">
            <button
              className="pixel-btn primary"
              onClick={authMode === 'login' ? onLogin : onSignup}
              disabled={authLoading || !authEmail || !authPassword}
            >
              {authLoading ? '[...]' : authMode === 'login' ? '[LOG IN]' : '[SIGN UP]'}
            </button>
            <button className="pixel-btn secondary" onClick={onClose}>
              [CANCEL]
            </button>
          </div>

          <p className="auth-switch">
            {authMode === 'login' ? (
              <>Don't have an account? <button className="link-btn" onClick={() => onSwitchMode('signup')}>Sign up</button></>
            ) : (
              <>Already have an account? <button className="link-btn" onClick={() => onSwitchMode('login')}>Log in</button></>
            )}
          </p>
        </div>
      </div>
    </div>
  )
}
