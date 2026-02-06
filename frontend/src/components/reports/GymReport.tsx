import RedFlagList from './RedFlagList'
import LetterView from './LetterView'
import { getRiskColor, getRiskLabel } from './utils'

interface ContractRedFlag {
  name: string
  severity: 'critical' | 'warning' | 'info'
  clause_text?: string
  explanation: string
  protection: string
}

interface GymContractReport {
  overall_risk: string
  risk_score: number
  gym_name?: string
  contract_type: string
  monthly_fee?: string
  cancellation_difficulty: string
  red_flags: ContractRedFlag[]
  state_protections: string[]
  summary: string
  cancellation_guide: string
}

interface GymReportProps {
  report: GymContractReport
  tab: 'report' | 'letter'
  setTab: (tab: 'report' | 'letter') => void
}

export default function GymReport({ report, tab, setTab }: GymReportProps) {
  return (
    <section className="output-section gym-output">
      <div className="compliance-header">
        <div
          className="compliance-status-badge"
          style={{ backgroundColor: getRiskColor(report.overall_risk) }}
        >
          {getRiskLabel(report.overall_risk)}
        </div>
        <div className="risk-exposure">
          <span className="label">CANCEL DIFFICULTY:</span>
          <span className="value">{report.cancellation_difficulty.toUpperCase()}</span>
        </div>
      </div>

      <p className="summary-text">{report.summary}</p>

      <div className="tabs">
        <button
          className={`tab ${tab === 'report' ? 'active' : ''}`}
          onClick={() => setTab('report')}
        >
          * ANALYSIS
        </button>
        <button
          className={`tab ${tab === 'letter' ? 'active' : ''}`}
          onClick={() => setTab('letter')}
        >
          * CANCELLATION GUIDE
        </button>
      </div>

      {tab === 'report' && (
        <div className="compliance-report">
          <RedFlagList flags={report.red_flags} />

          {report.state_protections.length > 0 && (
            <div className="data-card success full-width">
              <h3>** YOUR STATE PROTECTIONS</h3>
              <div className="missing-list">
                {report.state_protections.map((item, i) => (
                  <div key={i} className="missing-item">
                    <span className="status-icon">✓</span>
                    <span>{item}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="data-card full-width">
            <h3>* CONTRACT INFO</h3>
            <div className="coi-data-grid">
              <div className="data-row">
                <span className="label">GYM:</span>
                <span className="value">{report.gym_name || '---'}</span>
              </div>
              <div className="data-row">
                <span className="label">TYPE:</span>
                <span className="value">{report.contract_type?.toUpperCase() || '---'}</span>
              </div>
              <div className="data-row">
                <span className="label">MONTHLY:</span>
                <span className="value mono">{report.monthly_fee || '---'}</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {tab === 'letter' && (
        <LetterView text={report.cancellation_guide} copyLabel="COPY GUIDE" />
      )}
    </section>
  )
}
