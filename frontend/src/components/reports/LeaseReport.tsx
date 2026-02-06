import RedFlagList from './RedFlagList'
import LetterView from './LetterView'
import { getRiskColor, getRiskLabel } from './utils'

interface LeaseInsuranceClause {
  clause_type: string
  original_text: string
  summary: string
  risk_level: 'high' | 'medium' | 'low'
  explanation: string
  recommendation: string
}

interface LeaseRedFlag {
  name: string
  severity: 'critical' | 'warning' | 'info'
  clause_text?: string
  explanation: string
  protection: string
}

interface LeaseAnalysisReport {
  overall_risk: 'high' | 'medium' | 'low'
  risk_score: number
  lease_type: string
  landlord_name?: string
  tenant_name?: string
  property_address?: string
  lease_term?: string
  insurance_requirements: LeaseInsuranceClause[]
  red_flags: LeaseRedFlag[]
  missing_protections: string[]
  summary: string
  negotiation_letter: string
}

interface LeaseReportProps {
  report: LeaseAnalysisReport
  tab: 'report' | 'letter'
  setTab: (tab: 'report' | 'letter') => void
}

export default function LeaseReport({ report, tab, setTab }: LeaseReportProps) {
  return (
    <section className="output-section lease-output">
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
          * NEGOTIATION LETTER
        </button>
      </div>

      {tab === 'report' && (
        <div className="compliance-report">
          <RedFlagList flags={report.red_flags} />

          {/* Missing Protections */}
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

          {/* Insurance Requirements Found */}
          {report.insurance_requirements.length > 0 && (
            <div className="data-card full-width">
              <h3>* INSURANCE REQUIREMENTS</h3>
              <div className="compliance-items">
                {report.insurance_requirements.map((req, i) => (
                  <div key={i} className={`compliance-item ${req.risk_level === 'high' ? 'fail' : req.risk_level === 'medium' ? 'warning' : 'pass'}`}>
                    <div className="item-header">
                      <span className="status-icon">{req.risk_level === 'high' ? '!' : req.risk_level === 'medium' ? '~' : '✓'}</span>
                      <span className="item-name">{req.summary}</span>
                    </div>
                    <p className="item-explanation">{req.explanation}</p>
                    <div className="protection-box">
                      <span className="label">DO:</span>
                      <span className="value">{req.recommendation}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Lease Info */}
          <div className="data-card full-width">
            <h3>* LEASE INFO</h3>
            <div className="coi-data-grid">
              <div className="data-row">
                <span className="label">TYPE:</span>
                <span className="value">{report.lease_type?.toUpperCase() || '---'}</span>
              </div>
              <div className="data-row">
                <span className="label">LANDLORD:</span>
                <span className="value">{report.landlord_name || '---'}</span>
              </div>
              <div className="data-row">
                <span className="label">TENANT:</span>
                <span className="value">{report.tenant_name || '---'}</span>
              </div>
              <div className="data-row">
                <span className="label">PROPERTY:</span>
                <span className="value">{report.property_address || '---'}</span>
              </div>
              <div className="data-row">
                <span className="label">TERM:</span>
                <span className="value">{report.lease_term || '---'}</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {tab === 'letter' && (
        <LetterView text={report.negotiation_letter} copyLabel="COPY LETTER" />
      )}
    </section>
  )
}
