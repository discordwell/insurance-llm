import LetterView from './LetterView'
import { getStatusColor, getStatusLabel } from './utils'

interface ExtractionMetadata {
  overall_confidence: number
  needs_human_review: boolean
  review_reasons: string[]
  low_confidence_fields: string[]
  extraction_notes?: string
}

interface COIData {
  insured_name?: string
  policy_number?: string
  carrier?: string
  effective_date?: string
  expiration_date?: string
  gl_limit_per_occurrence?: string
  gl_limit_aggregate?: string
  workers_comp: boolean
  auto_liability: boolean
  umbrella_limit?: string
  additional_insured_checked: boolean
  waiver_of_subrogation_checked: boolean
  primary_noncontributory: boolean
  certificate_holder?: string
  description_of_operations?: string
  cg_20_10_endorsement: boolean
  cg_20_37_endorsement: boolean
}

interface ComplianceRequirement {
  name: string
  required_value: string
  actual_value: string
  status: 'pass' | 'fail' | 'warning'
  explanation: string
}

interface ComplianceReport {
  overall_status: 'compliant' | 'non-compliant' | 'needs-review'
  coi_data: COIData
  critical_gaps: ComplianceRequirement[]
  warnings: ComplianceRequirement[]
  passed: ComplianceRequirement[]
  risk_exposure: string
  fix_request_letter: string
  extraction_metadata?: ExtractionMetadata
}

interface COIReportProps {
  report: ComplianceReport
  tab: 'report' | 'letter'
  setTab: (tab: 'report' | 'letter') => void
}

export default function COIReport({ report, tab, setTab }: COIReportProps) {
  return (
    <section className="output-section compliance-output">
      <div className="compliance-header">
        <div
          className="compliance-status-badge"
          style={{ backgroundColor: getStatusColor(report.overall_status) }}
        >
          {getStatusLabel(report.overall_status)}
        </div>
        <div className="risk-exposure">
          <span className="label">RISK EXPOSURE:</span>
          <span className="value">{report.risk_exposure}</span>
        </div>
      </div>

      {/* Confidence Banner */}
      {report.extraction_metadata && (
        <div className={`confidence-banner ${report.extraction_metadata.needs_human_review ? 'needs-review' : 'confident'}`}>
          <div className="confidence-header">
            <span className="confidence-icon">
              {report.extraction_metadata.needs_human_review ? '[?]' : '[✓]'}
            </span>
            <span className="confidence-label">EXTRACTION CONFIDENCE:</span>
            <span className={`confidence-value ${report.extraction_metadata.overall_confidence >= 0.8 ? 'high' : report.extraction_metadata.overall_confidence >= 0.6 ? 'medium' : 'low'}`}>
              {Math.round(report.extraction_metadata.overall_confidence * 100)}%
            </span>
          </div>
          {report.extraction_metadata.needs_human_review && (
            <div className="review-warning">
              <span className="warning-text">HUMAN REVIEW RECOMMENDED</span>
              {report.extraction_metadata.review_reasons.length > 0 && (
                <ul className="review-reasons">
                  {report.extraction_metadata.review_reasons.slice(0, 3).map((reason, i) => (
                    <li key={i}>{reason}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
          {report.extraction_metadata.low_confidence_fields.length > 0 && (
            <div className="low-confidence-fields">
              <span className="label">LOW CONFIDENCE:</span>
              {report.extraction_metadata.low_confidence_fields.map((field, i) => (
                <span key={i} className="field-badge">{field.replace(/_/g, ' ')}</span>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="tabs">
        <button
          className={`tab ${tab === 'report' ? 'active' : ''}`}
          onClick={() => setTab('report')}
        >
          * COMPLIANCE REPORT
        </button>
        <button
          className={`tab ${tab === 'letter' ? 'active' : ''}`}
          onClick={() => setTab('letter')}
        >
          * FIX REQUEST LETTER
        </button>
      </div>

      {tab === 'report' && (
        <div className="compliance-report">
          {report.critical_gaps.length > 0 && (
            <div className="data-card danger full-width">
              <h3>XX CRITICAL GAPS ({report.critical_gaps.length})</h3>
              <div className="compliance-items">
                {report.critical_gaps.map((gap, i) => (
                  <div key={i} className="compliance-item fail">
                    <div className="item-header">
                      <span className="status-icon">✗</span>
                      <span className="item-name">{gap.name}</span>
                    </div>
                    <div className="item-details">
                      <div className="detail-row">
                        <span className="label">REQUIRED:</span>
                        <span className="value">{gap.required_value}</span>
                      </div>
                      <div className="detail-row">
                        <span className="label">ACTUAL:</span>
                        <span className="value">{gap.actual_value}</span>
                      </div>
                    </div>
                    <p className="item-explanation">{gap.explanation}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {report.warnings.length > 0 && (
            <div className="data-card warning full-width">
              <h3>!! WARNINGS ({report.warnings.length})</h3>
              <div className="compliance-items">
                {report.warnings.map((warn, i) => (
                  <div key={i} className="compliance-item warning">
                    <div className="item-header">
                      <span className="status-icon">!</span>
                      <span className="item-name">{warn.name}</span>
                    </div>
                    <div className="item-details">
                      <div className="detail-row">
                        <span className="label">REQUIRED:</span>
                        <span className="value">{warn.required_value}</span>
                      </div>
                      <div className="detail-row">
                        <span className="label">ACTUAL:</span>
                        <span className="value">{warn.actual_value}</span>
                      </div>
                    </div>
                    <p className="item-explanation">{warn.explanation}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {report.passed.length > 0 && (
            <div className="data-card success full-width">
              <h3>** PASSED ({report.passed.length})</h3>
              <div className="compliance-items compact">
                {report.passed.map((item, i) => (
                  <div key={i} className="compliance-item pass">
                    <div className="item-header">
                      <span className="status-icon">✓</span>
                      <span className="item-name">{item.name}</span>
                      <span className="item-value">{item.actual_value}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="data-card full-width">
            <h3>* COI DATA EXTRACTED</h3>
            <div className="coi-data-grid">
              <div className="data-row">
                <span className="label">INSURED:</span>
                <span className="value">{report.coi_data.insured_name || '---'}</span>
              </div>
              <div className="data-row">
                <span className="label">GL PER OCC:</span>
                <span className="value mono">{report.coi_data.gl_limit_per_occurrence || '---'}</span>
              </div>
              <div className="data-row">
                <span className="label">GL AGGREGATE:</span>
                <span className="value mono">{report.coi_data.gl_limit_aggregate || '---'}</span>
              </div>
              <div className="data-row">
                <span className="label">UMBRELLA:</span>
                <span className="value mono">{report.coi_data.umbrella_limit || '---'}</span>
              </div>
              <div className="data-row">
                <span className="label">ADD'L INSURED:</span>
                <span className={`value ${report.coi_data.additional_insured_checked ? 'pass' : 'fail'}`}>
                  {report.coi_data.additional_insured_checked ? 'YES' : 'NO'}
                </span>
              </div>
              <div className="data-row">
                <span className="label">WAIVER SUB:</span>
                <span className={`value ${report.coi_data.waiver_of_subrogation_checked ? 'pass' : 'fail'}`}>
                  {report.coi_data.waiver_of_subrogation_checked ? 'YES' : 'NO'}
                </span>
              </div>
              <div className="data-row">
                <span className="label">CG 20 10:</span>
                <span className={`value ${report.coi_data.cg_20_10_endorsement ? 'pass' : ''}`}>
                  {report.coi_data.cg_20_10_endorsement ? 'YES' : 'NO'}
                </span>
              </div>
              <div className="data-row">
                <span className="label">CG 20 37:</span>
                <span className={`value ${report.coi_data.cg_20_37_endorsement ? 'pass' : ''}`}>
                  {report.coi_data.cg_20_37_endorsement ? 'YES' : 'NO'}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {tab === 'letter' && (
        <LetterView text={report.fix_request_letter} copyLabel="COPY LETTER" />
      )}
    </section>
  )
}
