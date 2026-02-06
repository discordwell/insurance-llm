import RedFlagList from './RedFlagList'
import LetterView from './LetterView'
import { getRiskColor, getRiskLabel } from './utils'

interface InsurancePolicyRedFlag {
  name: string
  severity: 'critical' | 'warning' | 'info'
  clause_text?: string
  explanation: string
  what_to_ask: string
}

interface InsurancePolicyReportData {
  overall_risk: string
  risk_score: number
  policy_type: string
  carrier?: string
  coverage_type: string
  valuation_method: string
  deductible_type: string
  has_arbitration: boolean
  red_flags: InsurancePolicyRedFlag[]
  coverage_gaps: string[]
  summary: string
  questions_for_agent: string
}

interface InsurancePolicyReportProps {
  report: InsurancePolicyReportData
  tab: 'report' | 'letter'
  setTab: (tab: 'report' | 'letter') => void
}

export default function InsurancePolicyReport({ report, tab, setTab }: InsurancePolicyReportProps) {
  return (
    <section className="output-section insurance-policy-output">
      <div className="compliance-header">
        <div
          className="compliance-status-badge"
          style={{ backgroundColor: getRiskColor(report.overall_risk) }}
        >
          {getRiskLabel(report.overall_risk)}
        </div>
        <div className="risk-exposure">
          <span className="label">VALUATION:</span>
          <span className={`value ${report.valuation_method === 'actual_cash_value' ? 'fail' : ''}`}>
            {report.valuation_method?.replace(/_/g, ' ').toUpperCase() || '---'}
          </span>
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
          * QUESTIONS FOR AGENT
        </button>
      </div>

      {tab === 'report' && (
        <div className="compliance-report">
          <RedFlagList flags={report.red_flags} protectionLabel="ASK AGENT" />

          {report.coverage_gaps.length > 0 && (
            <div className="data-card info full-width">
              <h3>?? COVERAGE GAPS</h3>
              <div className="missing-list">
                {report.coverage_gaps.map((item, i) => (
                  <div key={i} className="missing-item">
                    <span className="status-icon">-</span>
                    <span>{item}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="data-card full-width">
            <h3>* POLICY INFO</h3>
            <div className="coi-data-grid">
              <div className="data-row">
                <span className="label">TYPE:</span>
                <span className="value">{report.policy_type?.toUpperCase() || '---'}</span>
              </div>
              <div className="data-row">
                <span className="label">CARRIER:</span>
                <span className="value">{report.carrier || '---'}</span>
              </div>
              <div className="data-row">
                <span className="label">COVERAGE:</span>
                <span className="value">{report.coverage_type?.replace(/_/g, ' ').toUpperCase() || '---'}</span>
              </div>
              <div className="data-row">
                <span className="label">DEDUCTIBLE:</span>
                <span className={`value ${report.deductible_type === 'percentage' ? 'fail' : ''}`}>
                  {report.deductible_type?.toUpperCase() || '---'}
                </span>
              </div>
              <div className="data-row">
                <span className="label">ARBITRATION:</span>
                <span className={`value ${report.has_arbitration ? 'fail' : 'pass'}`}>
                  {report.has_arbitration ? 'YES' : 'NO'}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {tab === 'letter' && (
        <LetterView text={report.questions_for_agent} copyLabel="COPY QUESTIONS" />
      )}
    </section>
  )
}
