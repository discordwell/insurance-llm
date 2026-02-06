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

interface FreelancerContractReport {
  overall_risk: string
  risk_score: number
  contract_type: string
  payment_terms?: string
  ip_ownership: string
  has_kill_fee: boolean
  revision_limit?: string
  red_flags: ContractRedFlag[]
  missing_protections: string[]
  summary: string
  suggested_changes: string
}

interface FreelancerReportProps {
  report: FreelancerContractReport
  tab: 'report' | 'letter'
  setTab: (tab: 'report' | 'letter') => void
}

export default function FreelancerReport({ report, tab, setTab }: FreelancerReportProps) {
  return (
    <section className="output-section freelancer-output">
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
          * SUGGESTED CHANGES
        </button>
      </div>

      {tab === 'report' && (
        <div className="compliance-report">
          <RedFlagList flags={report.red_flags} />

          {report.missing_protections.length > 0 && (
            <div className="data-card info full-width">
              <h3>?? MISSING PROTECTIONS</h3>
              <div className="missing-list">
                {report.missing_protections.map((item, i) => (
                  <div key={i} className="missing-item">
                    <span className="status-icon">-</span>
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
                <span className="value">{report.contract_type?.toUpperCase() || '---'}</span>
              </div>
              <div className="data-row">
                <span className="label">PAYMENT:</span>
                <span className="value">{report.payment_terms || '---'}</span>
              </div>
              <div className="data-row">
                <span className="label">IP OWNERSHIP:</span>
                <span className="value">{report.ip_ownership?.replace(/_/g, ' ').toUpperCase() || '---'}</span>
              </div>
              <div className="data-row">
                <span className="label">KILL FEE:</span>
                <span className={`value ${report.has_kill_fee ? 'pass' : 'fail'}`}>
                  {report.has_kill_fee ? 'YES' : 'NO'}
                </span>
              </div>
              <div className="data-row">
                <span className="label">REVISIONS:</span>
                <span className="value">{report.revision_limit || 'UNLIMITED'}</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {tab === 'letter' && (
        <LetterView text={report.suggested_changes} copyLabel="COPY CHANGES" />
      )}
    </section>
  )
}
