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

interface TimeshareContractReport {
  overall_risk: string
  risk_score: number
  resort_name?: string
  ownership_type: string
  has_perpetuity_clause: boolean
  rescission_deadline?: string
  estimated_10yr_cost?: string
  red_flags: ContractRedFlag[]
  exit_options: string[]
  summary: string
  rescission_letter: string
}

interface TimeshareReportProps {
  report: TimeshareContractReport
  tab: 'report' | 'letter'
  setTab: (tab: 'report' | 'letter') => void
}

export default function TimeshareReport({ report, tab, setTab }: TimeshareReportProps) {
  return (
    <section className="output-section timeshare-output">
      <div className="compliance-header">
        <div
          className="compliance-status-badge"
          style={{ backgroundColor: getRiskColor(report.overall_risk) }}
        >
          {getRiskLabel(report.overall_risk)}
        </div>
        <div className="risk-exposure">
          <span className="label">10-YEAR COST:</span>
          <span className="value">{report.estimated_10yr_cost || 'UNKNOWN'}</span>
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
          * RESCISSION LETTER
        </button>
      </div>

      {tab === 'report' && (
        <div className="compliance-report">
          <RedFlagList flags={report.red_flags} />

          {report.exit_options.length > 0 && (
            <div className="data-card info full-width">
              <h3>?? EXIT OPTIONS</h3>
              <div className="missing-list">
                {report.exit_options.map((item, i) => (
                  <div key={i} className="missing-item">
                    <span className="status-icon">{i + 1}.</span>
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
                <span className="label">RESORT:</span>
                <span className="value">{report.resort_name || '---'}</span>
              </div>
              <div className="data-row">
                <span className="label">OWNERSHIP:</span>
                <span className="value">{report.ownership_type?.replace(/_/g, ' ').toUpperCase() || '---'}</span>
              </div>
              <div className="data-row">
                <span className="label">PERPETUITY:</span>
                <span className={`value ${report.has_perpetuity_clause ? 'fail' : 'pass'}`}>
                  {report.has_perpetuity_clause ? 'YES - FOREVER' : 'NO'}
                </span>
              </div>
              <div className="data-row">
                <span className="label">RESCISSION:</span>
                <span className={`value ${report.rescission_deadline ? '' : 'fail'}`}>
                  {report.rescission_deadline || 'CHECK STATE LAW'}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {tab === 'letter' && (
        <LetterView text={report.rescission_letter} copyLabel="COPY LETTER" />
      )}
    </section>
  )
}
