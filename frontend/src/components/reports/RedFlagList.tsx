interface RedFlag {
  name: string
  severity: 'critical' | 'warning' | 'info'
  clause_text?: string
  explanation: string
  protection?: string
  what_to_ask?: string
}

interface RedFlagListProps {
  flags: RedFlag[]
  protectionLabel?: string
}

export default function RedFlagList({ flags, protectionLabel = 'PROTECTION' }: RedFlagListProps) {
  const criticalFlags = flags.filter(rf => rf.severity === 'critical')
  const warningFlags = flags.filter(rf => rf.severity === 'warning')

  return (
    <>
      {criticalFlags.length > 0 && (
        <div className="data-card danger full-width">
          <h3>XX CRITICAL RED FLAGS</h3>
          <div className="compliance-items">
            {criticalFlags.map((flag, i) => (
              <div key={i} className="compliance-item fail">
                <div className="item-header">
                  <span className="status-icon">&#10007;</span>
                  <span className="item-name">{flag.name}</span>
                </div>
                {flag.clause_text && (
                  <div className="clause-text">
                    <span className="label">CLAUSE:</span>
                    <span className="value">&quot;{flag.clause_text}&quot;</span>
                  </div>
                )}
                <p className="item-explanation">{flag.explanation}</p>
                <div className="protection-box">
                  <span className="label">{protectionLabel}:</span>
                  <span className="value">{flag.protection || flag.what_to_ask}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {warningFlags.length > 0 && (
        <div className="data-card warning full-width">
          <h3>!! WATCH OUT FOR</h3>
          <div className="compliance-items">
            {warningFlags.map((flag, i) => (
              <div key={i} className="compliance-item warning">
                <div className="item-header">
                  <span className="status-icon">!</span>
                  <span className="item-name">{flag.name}</span>
                </div>
                {flag.clause_text && (
                  <div className="clause-text">
                    <span className="label">CLAUSE:</span>
                    <span className="value">&quot;{flag.clause_text}&quot;</span>
                  </div>
                )}
                <p className="item-explanation">{flag.explanation}</p>
                <div className="protection-box">
                  <span className="label">{protectionLabel}:</span>
                  <span className="value">{flag.protection || flag.what_to_ask}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  )
}
