interface HeaderProps {
  isLoggedIn: boolean
  userEmail: string | null
  openHistoryModal: () => void
  handleLogout: () => void
  setAuthMode: (mode: 'login' | 'signup') => void
  setShowAuthModal: (show: boolean) => void
}

export default function Header({ isLoggedIn, userEmail, openHistoryModal, handleLogout, setAuthMode, setShowAuthModal }: HeaderProps) {
  return (
    <header className="header">
      <div className="header-row">
        <div className="logo">
          <span className="logo-icon">&#9043;</span>
          <h1>Can They Fuck Me?</h1>
        </div>
        <div className="auth-section">
          {isLoggedIn ? (
            <>
              <span className="user-email">{userEmail}</span>
              <button className="auth-btn" onClick={openHistoryModal}>History</button>
              <button className="auth-btn logout-btn" onClick={handleLogout}>Log Out</button>
            </>
          ) : (
            <button className="auth-btn signup-btn" onClick={() => { setAuthMode('signup'); setShowAuthModal(true) }}>
              Sign In to Save History
            </button>
          )}
        </div>
      </div>
      <p className="tagline">Upload your insurance policy, lease, or contract to see how it stacks up</p>
    </header>
  )
}
