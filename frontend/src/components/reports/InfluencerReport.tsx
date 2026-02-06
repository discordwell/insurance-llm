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

interface InfluencerContractReport {
  overall_risk: string
  risk_score: number
  brand_name?: string
  campaign_type: string
  usage_rights_duration?: string
  exclusivity_scope?: string
  payment_terms?: string
  has_perpetual_rights: boolean
  has_ai_training_rights: boolean
  ftc_compliance: string
  red_flags: ContractRedFlag[]
  summary: string
  negotiation_script: string
}

interface InfluencerReportProps {
  report: InfluencerContractReport
  tab: 'report' | 'letter'
  setTab: (tab: 'report' | 'letter') => void
}

export default function InfluencerReport({ report, tab, setTab }: InfluencerReportProps) {
  return (
    <section className="output-section influencer-output">
      <div className="compliance-header">
        <div
          className="compliance-status-badge"
          style={{ backgroundColor: getRiskColor(report.overall_risk) }}
        >
          {getRiskLabel(report.overall_risk)}
        </div>
        <div className="risk-exposure">
          <span className="label">FTC COMPLIANCE:</span>
          <span className={`value ${report.ftc_compliance === 'addressed' ? 'pass' : report.ftc_compliance === 'missing' ? 'fail' : ''}`}>
            {report.ftc_compliance.toUpperCase()}
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
          * NEGOTIATION SCRIPT
        </button>
      </div>

      {tab === 'report' && (
        <div className="compliance-report">
          <RedFlagList flags={report.red_flags} />

          <div className="data-card full-width">
            <h3>* CONTRACT INFO</h3>
            <div className="coi-data-grid">
              <div className="data-row">
                <span className="label">BRAND:</span>
                <span className="value">{report.brand_name || '---'}</span>
              </div>
              <div className="data-row">
                <span className="label">CAMPAIGN:</span>
                <span className="value">{report.campaign_type?.replace(/_/g, ' ').toUpperCase() || '---'}</span>
              </div>
              <div className="data-row">
                <span className="label">USAGE RIGHTS:</span>
                <span className="value">{report.usage_rights_duration || '---'}</span>
              </div>
              <div className="data-row">
                <span className="label">EXCLUSIVITY:</span>
                <span className="value">{report.exclusivity_scope || 'NONE'}</span>
              </div>
              <div className="data-row">
                <span className="label">PERPETUAL:</span>
                <span className={`value ${report.has_perpetual_rights ? 'fail' : 'pass'}`}>
                  {report.has_perpetual_rights ? 'YES' : 'NO'}
                </span>
              </div>
              <div className="data-row">
                <span className="label">AI TRAINING:</span>
                <span className={`value ${report.has_ai_training_rights ? 'fail' : 'pass'}`}>
                  {report.has_ai_training_rights ? 'YES' : 'NO'}
                </span>
              </div>
              <div className="data-row">
                <span className="label">PAYMENT:</span>
                <span className="value">{report.payment_terms || '---'}</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {tab === 'letter' && (
        <LetterView text={report.negotiation_script} copyLabel="COPY SCRIPT" />
      )}
    </section>
  )
}
