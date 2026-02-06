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

interface EmploymentContractReport {
  overall_risk: string
  risk_score: number
  document_type: string
  has_non_compete: boolean
  non_compete_enforceable?: string
  has_arbitration: boolean
  has_ip_assignment: boolean
  red_flags: ContractRedFlag[]
  state_notes: string[]
  summary: string
  negotiation_points: string
}

interface EmploymentReportProps {
  report: EmploymentContractReport
  tab: 'report' | 'letter'
  setTab: (tab: 'report' | 'letter') => void
}

export default function EmploymentReport({ report, tab, setTab }: EmploymentReportProps) {
  return (
    <section className="output-section employment-output">
      <div className="compliance-header">
        <div
          className="compliance-status-badge"
          style={{ backgroundColor: getRiskColor(report.overall_risk) }}
        >
          {getRiskLabel(report.overall_risk)}
        </div>
        <div className="risk-exposure">
          <span className="label">RISK SCORE:</span>
          <span className="value">{report.risk_score}/100</span>
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
          * NEGOTIATION POINTS
        </button>
      </div>

      {tab === 'report' && (
        <div className="compliance-report">
          <RedFlagList flags={report.red_flags} />

          {report.state_notes.length > 0 && (
            <div className="data-card info full-width">
              <h3>?? STATE-SPECIFIC NOTES</h3>
              <div className="missing-list">
                {report.state_notes.map((item, i) => (
                  <div key={i} className="missing-item">
                    <span className="status-icon">*</span>
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
                <span className="label">TYPE:</span>
                <span className="value">{report.document_type?.replace(/_/g, ' ').toUpperCase() || '---'}</span>
              </div>
              <div className="data-row">
                <span className="label">NON-COMPETE:</span>
                <span className={`value ${report.has_non_compete ? 'fail' : 'pass'}`}>
                  {report.has_non_compete ? 'YES' : 'NO'}
                </span>
              </div>
              {report.has_non_compete && (
                <div className="data-row">
                  <span className="label">ENFORCEABLE:</span>
                  <span className="value">{report.non_compete_enforceable?.toUpperCase() || '---'}</span>
                </div>
              )}
              <div className="data-row">
                <span className="label">ARBITRATION:</span>
                <span className={`value ${report.has_arbitration ? 'fail' : 'pass'}`}>
                  {report.has_arbitration ? 'YES' : 'NO'}
                </span>
              </div>
              <div className="data-row">
                <span className="label">IP ASSIGNMENT:</span>
                <span className={`value ${report.has_ip_assignment ? 'fail' : ''}`}>
                  {report.has_ip_assignment ? 'YES' : 'NO'}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {tab === 'letter' && (
        <LetterView text={report.negotiation_points} copyLabel="COPY POINTS" />
      )}
    </section>
  )
}
