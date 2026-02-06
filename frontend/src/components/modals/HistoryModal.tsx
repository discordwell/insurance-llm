interface HistoryItem {
  id: number
  created_at: string
  document_type: string
  overall_risk: string
  risk_score: number
}

interface HistoryModalProps {
  show: boolean
  historyLoading: boolean
  userHistory: HistoryItem[]
  onClose: () => void
}

export default function HistoryModal({ show, historyLoading, userHistory, onClose }: HistoryModalProps) {
  if (!show) return null

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal history-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <span className="modal-icon">[H]</span>
          <h2>YOUR HISTORY</h2>
        </div>
        <div className="modal-content">
          {historyLoading ? (
            <p className="loading-text">Loading...</p>
          ) : userHistory.length === 0 ? (
            <p>No documents analyzed yet. Upload one to get started!</p>
          ) : (
            <div className="history-list">
              {userHistory.map((item) => (
                <div key={item.id} className="history-item">
                  <div className="history-item-header">
                    <span className="history-type">{item.document_type.toUpperCase()}</span>
                    <span className={`history-risk risk-${item.overall_risk}`}>
                      {item.overall_risk.toUpperCase()}
                    </span>
                  </div>
                  <div className="history-item-meta">
                    <span className="history-score">Score: {item.risk_score}/100</span>
                    <span className="history-date">
                      {new Date(item.created_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
          <div className="modal-buttons">
            <button className="pixel-btn secondary" onClick={onClose}>
              [CLOSE]
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
