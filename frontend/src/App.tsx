import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import './App.css'

// API base URL - uses environment variable in production, localhost in dev
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8081'

// COI Compliance Types
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
}

// US States for compliance checking
const US_STATES = [
  { code: '', name: 'Select State (optional)' },
  { code: 'AL', name: 'Alabama' },
  { code: 'AK', name: 'Alaska' },
  { code: 'AZ', name: 'Arizona' },
  { code: 'AR', name: 'Arkansas' },
  { code: 'CA', name: 'California' },
  { code: 'CO', name: 'Colorado' },
  { code: 'CT', name: 'Connecticut' },
  { code: 'DE', name: 'Delaware' },
  { code: 'FL', name: 'Florida' },
  { code: 'GA', name: 'Georgia' },
  { code: 'HI', name: 'Hawaii' },
  { code: 'ID', name: 'Idaho' },
  { code: 'IL', name: 'Illinois' },
  { code: 'IN', name: 'Indiana' },
  { code: 'IA', name: 'Iowa' },
  { code: 'KS', name: 'Kansas' },
  { code: 'KY', name: 'Kentucky' },
  { code: 'LA', name: 'Louisiana' },
  { code: 'ME', name: 'Maine' },
  { code: 'MD', name: 'Maryland' },
  { code: 'MA', name: 'Massachusetts' },
  { code: 'MI', name: 'Michigan' },
  { code: 'MN', name: 'Minnesota' },
  { code: 'MS', name: 'Mississippi' },
  { code: 'MO', name: 'Missouri' },
  { code: 'MT', name: 'Montana' },
  { code: 'NE', name: 'Nebraska' },
  { code: 'NV', name: 'Nevada' },
  { code: 'NH', name: 'New Hampshire' },
  { code: 'NJ', name: 'New Jersey' },
  { code: 'NM', name: 'New Mexico' },
  { code: 'NY', name: 'New York' },
  { code: 'NC', name: 'North Carolina' },
  { code: 'ND', name: 'North Dakota' },
  { code: 'OH', name: 'Ohio' },
  { code: 'OK', name: 'Oklahoma' },
  { code: 'OR', name: 'Oregon' },
  { code: 'PA', name: 'Pennsylvania' },
  { code: 'RI', name: 'Rhode Island' },
  { code: 'SC', name: 'South Carolina' },
  { code: 'SD', name: 'South Dakota' },
  { code: 'TN', name: 'Tennessee' },
  { code: 'TX', name: 'Texas' },
  { code: 'UT', name: 'Utah' },
  { code: 'VT', name: 'Vermont' },
  { code: 'VA', name: 'Virginia' },
  { code: 'WA', name: 'Washington' },
  { code: 'WV', name: 'West Virginia' },
  { code: 'WI', name: 'Wisconsin' },
  { code: 'WY', name: 'Wyoming' },
  { code: 'DC', name: 'District of Columbia' },
]

// States with broad anti-indemnity statutes - AI coverage limitations
const AI_LIMITED_STATES: Record<string, { mitigation: string[] }> = {
  'AZ': { mitigation: ['CG 24 26 endorsement (excludes your negligence from AI)', 'Higher primary limits on your own CGL'] },
  'CO': { mitigation: ['Wrap-up/OCIP for larger projects', 'Contractual liability coverage on your policy', 'Explicit fault allocation in subcontracts'] },
  'GA': { mitigation: ['Primary & non-contributory language still valid', 'Ensure your own CGL has adequate limits'] },
  'KS': { mitigation: ['Wrap-up programs', 'Higher umbrella limits on your policy'] },
  'MT': { mitigation: ['OCIP/CCIP wrap-up insurance', 'Project-specific coverage', 'Your own policy must be primary'] },
  'OR': { mitigation: ['CG 24 26 amendment endorsement', 'Contractual liability on your CGL'] },
}

const SAMPLE_COIS = [
  {
    name: "Non-Compliant COI",
    text: `CERTIFICATE OF LIABILITY INSURANCE
DATE: 01/15/2024

PRODUCER: ABC Insurance Agency
123 Main St, Anytown, USA

INSURED: Smith Electrical LLC
456 Oak Ave, Anytown, USA

THIS CERTIFICATE IS ISSUED AS A MATTER OF INFORMATION ONLY AND CONFERS NO RIGHTS UPON THE CERTIFICATE HOLDER.

COVERAGES:
Commercial General Liability
  Each Occurrence: $500,000
  General Aggregate: $1,000,000
  Products/Completed Ops: $500,000
  Personal & Adv Injury: $500,000

Workers Compensation: YES - Statutory Limits

Automobile Liability: $500,000 Combined Single Limit

CERTIFICATE HOLDER:
Johnson Construction Co.
789 Builder Blvd
Anytown, USA 12345

[X] Additional Insured (see attached)
[ ] Waiver of Subrogation

DESCRIPTION OF OPERATIONS:
Electrical work at Main St Office Building project

Policy Period: 01/01/2024 to 01/01/2025`
  },
  {
    name: "Compliant COI",
    text: `CERTIFICATE OF LIABILITY INSURANCE
DATE: 01/15/2024

PRODUCER: Premier Insurance Brokers
500 Commerce Way, Metro City, USA

INSURED: Elite Mechanical Contractors Inc
1200 Industrial Pkwy, Metro City, USA

COVERAGES:
Commercial General Liability (CG 20 10, CG 20 37 endorsements attached)
  Each Occurrence: $1,000,000
  General Aggregate: $2,000,000
  Products/Completed Ops: $2,000,000
  Personal & Adv Injury: $1,000,000

Workers Compensation: YES - Statutory Limits
  Employer's Liability: $1,000,000

Automobile Liability: $1,000,000 Combined Single Limit

Umbrella/Excess Liability: $5,000,000

CERTIFICATE HOLDER:
Apex General Contractors LLC
999 Tower Plaza, Suite 100
Metro City, USA 54321

[X] Additional Insured - CG 20 10 07/04, CG 20 37 07/04
[X] Waiver of Subrogation
[X] Primary and Non-Contributory

DESCRIPTION OF OPERATIONS:
HVAC installation and mechanical work at Metro Tower Development.
Apex General Contractors LLC is named as Additional Insured per written contract.

Policy Period: 01/01/2024 to 01/01/2025`
  },
  {
    name: "Missing Endorsements",
    text: `CERTIFICATE OF LIABILITY INSURANCE
DATE: 02/01/2024

PRODUCER: QuickCover Insurance
Online Quote #QC-2024-8821

INSURED: Rapid Roofing Services
PO Box 445, Suburbia, USA

COVERAGES:
Commercial General Liability
  Each Occurrence: $1,000,000
  General Aggregate: $2,000,000

Workers Compensation: YES - Statutory

Auto Liability: $1,000,000

CERTIFICATE HOLDER:
Homebuilders Inc
123 Development Dr
Suburbia, USA

[X] Additional Insured
[ ] Waiver of Subrogation

DESCRIPTION OF OPERATIONS:
Roofing work - various residential projects

NOTE: Certificate holder is listed for information purposes only.

Policy: 01/15/2024 - 01/15/2025`
  }
]


function App() {
  const [loading, setLoading] = useState(false)
  const [ocrLoading, setOcrLoading] = useState(false)
  const [scanLines] = useState(true)
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null)

  // COI Compliance State
  const [coiText, setCoiText] = useState('')
  const [projectType, setProjectType] = useState('commercial_construction')
  const [selectedState, setSelectedState] = useState('')
  const [complianceReport, setComplianceReport] = useState<ComplianceReport | null>(null)
  const [complianceTab, setComplianceTab] = useState<'report' | 'letter'>('report')

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    const file = acceptedFiles[0]
    if (!file) return

    setUploadedFileName(file.name)
    setComplianceReport(null)

    // For text files, read directly
    if (file.type === 'text/plain') {
      const reader = new FileReader()
      reader.onload = () => {
        setCoiText(reader.result as string)
      }
      reader.readAsText(file)
      return
    }

    // For PDFs and images, send to OCR endpoint
    setOcrLoading(true)
    try {
      const base64 = await fileToBase64(file)
      const res = await fetch(`${API_BASE}/api/ocr`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          file_data: base64,
          file_type: file.type,
          file_name: file.name
        })
      })

      if (!res.ok) throw new Error('OCR failed')
      const data = await res.json()
      setCoiText(data.text)
    } catch (err) {
      console.error(err)
      alert('Failed to process file. Make sure the backend is running!')
    } finally {
      setOcrLoading(false)
    }
  }, [])

  const fileToBase64 = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.readAsDataURL(file)
      reader.onload = () => {
        const result = reader.result as string
        // Remove data URL prefix (e.g., "data:application/pdf;base64,")
        const base64 = result.split(',')[1]
        resolve(base64)
      }
      reader.onerror = reject
    })
  }

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'image/*': ['.png', '.jpg', '.jpeg', '.gif', '.webp'],
      'text/plain': ['.txt']
    },
    multiple: false
  })

  const loadCoiSample = (sample: typeof SAMPLE_COIS[0]) => {
    setCoiText(sample.text)
    setComplianceReport(null)
    setUploadedFileName(null)
  }

  const handleCheckCompliance = async () => {
    if (!coiText.trim()) return
    setLoading(true)
    setComplianceReport(null)

    try {
      const res = await fetch(`${API_BASE}/api/check-coi-compliance`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          coi_text: coiText,
          project_type: projectType,
          state: selectedState || null
        })
      })

      if (!res.ok) throw new Error('Compliance check failed')
      const data = await res.json()
      setComplianceReport(data)
      setComplianceTab('report')
    } catch (err) {
      console.error(err)
      alert('Failed to check compliance. Make sure the backend is running!')
    } finally {
      setLoading(false)
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'pass':
      case 'compliant':
        return 'var(--pixel-green)'
      case 'warning':
      case 'needs-review':
        return 'var(--pixel-yellow)'
      case 'fail':
      case 'non-compliant':
        return 'var(--pixel-red)'
      default:
        return 'var(--pixel-gray)'
    }
  }

  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'compliant':
        return 'COMPLIANT'
      case 'non-compliant':
        return 'NON-COMPLIANT'
      case 'needs-review':
        return 'NEEDS REVIEW'
      default:
        return status.toUpperCase()
    }
  }

  return (
    <div className={`app ${scanLines ? 'scanlines' : ''}`}>
      <header className="header">
        <div className="logo">
          <span className="logo-icon">&#9043;</span>
          <h1>Can They Fuck Me?</h1>
        </div>
        <p className="tagline">Upload your insurance policy, lease, or contract to see how it stacks up against best practices and state standards</p>
      </header>

      <main className="main">
        <section className="input-section">
          <div {...getRootProps()} className={`dropzone ${isDragActive ? 'active' : ''} ${ocrLoading ? 'processing' : ''}`}>
            <input {...getInputProps()} />
            <div className="dropzone-content">
              {ocrLoading ? (
                <>
                  <span className="dropzone-icon">[...]</span>
                  <p>READING DOCUMENT...</p>
                </>
              ) : isDragActive ? (
                <>
                  <span className="dropzone-icon">[+]</span>
                  <p>DROP IT</p>
                </>
              ) : (
                <>
                  <span className="dropzone-icon">[FILE]</span>
                  <p>drop PDF, image, or text file here</p>
                  <p className="dropzone-hint">or click to browse</p>
                </>
              )}
            </div>
          </div>

          {uploadedFileName && (
            <div className="uploaded-file">
              <span className="file-label">LOADED:</span>
              <span className="file-name">{uploadedFileName}</span>
              <button
                className="clear-btn"
                onClick={() => { setUploadedFileName(null); setCoiText(''); setComplianceReport(null); }}
              >
                [X]
              </button>
            </div>
          )}

          <textarea
            className="doc-input"
            value={coiText}
            onChange={(e) => setCoiText(e.target.value)}
            placeholder="...or paste text here"
            rows={8}
          />

          <div className="options-row">
            <div className="option-group">
              <span className="label">TYPE:</span>
              <select
                className="pixel-select"
                value={projectType}
                onChange={(e) => setProjectType(e.target.value)}
              >
                <option value="commercial_construction">Commercial ($1M/$2M)</option>
                <option value="residential_construction">Residential ($500K/$1M)</option>
                <option value="government_municipal">Government ($2M/$4M)</option>
                <option value="industrial_manufacturing">Industrial ($2M/$4M)</option>
              </select>
            </div>

            <div className="option-group">
              <span className="label">STATE:</span>
              <select
                className="pixel-select"
                value={selectedState}
                onChange={(e) => setSelectedState(e.target.value)}
              >
                {US_STATES.map((state) => (
                  <option key={state.code} value={state.code}>
                    {state.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {AI_LIMITED_STATES[selectedState] && (
            <div className="state-warning">
              !! {selectedState} limits Additional Insured coverage for shared fault
            </div>
          )}

          <button
            className={`pixel-btn primary ${loading ? 'loading' : ''}`}
            onClick={handleCheckCompliance}
            disabled={loading || ocrLoading || !coiText.trim()}
          >
            {loading ? '[ ANALYZING... ]' : '> CAN THEY FUCK ME?'}
          </button>

          <div className="sample-docs">
            <span className="label">or try a sample:</span>
            {SAMPLE_COIS.map((doc, i) => (
              <button key={i} className="pixel-btn small" onClick={() => loadCoiSample(doc)}>
                {doc.name}
              </button>
            ))}
          </div>
        </section>

        {complianceReport && (
          <section className="output-section compliance-output">
            <div className="compliance-header">
              <div
                className="compliance-status-badge"
                style={{ backgroundColor: getStatusColor(complianceReport.overall_status) }}
              >
                {getStatusLabel(complianceReport.overall_status)}
              </div>
              <div className="risk-exposure">
                <span className="label">RISK EXPOSURE:</span>
                <span className="value">{complianceReport.risk_exposure}</span>
              </div>
            </div>

            <div className="tabs">
              <button
                className={`tab ${complianceTab === 'report' ? 'active' : ''}`}
                onClick={() => setComplianceTab('report')}
              >
                * COMPLIANCE REPORT
              </button>
              <button
                className={`tab ${complianceTab === 'letter' ? 'active' : ''}`}
                onClick={() => setComplianceTab('letter')}
              >
                * FIX REQUEST LETTER
              </button>
            </div>

            {complianceTab === 'report' && (
              <div className="compliance-report">
                {complianceReport.critical_gaps.length > 0 && (
                  <div className="data-card danger full-width">
                    <h3>XX CRITICAL GAPS ({complianceReport.critical_gaps.length})</h3>
                    <div className="compliance-items">
                      {complianceReport.critical_gaps.map((gap, i) => (
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

                {complianceReport.warnings.length > 0 && (
                  <div className="data-card warning full-width">
                    <h3>!! WARNINGS ({complianceReport.warnings.length})</h3>
                    <div className="compliance-items">
                      {complianceReport.warnings.map((warn, i) => (
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

                {complianceReport.passed.length > 0 && (
                  <div className="data-card success full-width">
                    <h3>** PASSED ({complianceReport.passed.length})</h3>
                    <div className="compliance-items compact">
                      {complianceReport.passed.map((item, i) => (
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
                      <span className="value">{complianceReport.coi_data.insured_name || '---'}</span>
                    </div>
                    <div className="data-row">
                      <span className="label">GL PER OCC:</span>
                      <span className="value mono">{complianceReport.coi_data.gl_limit_per_occurrence || '---'}</span>
                    </div>
                    <div className="data-row">
                      <span className="label">GL AGGREGATE:</span>
                      <span className="value mono">{complianceReport.coi_data.gl_limit_aggregate || '---'}</span>
                    </div>
                    <div className="data-row">
                      <span className="label">UMBRELLA:</span>
                      <span className="value mono">{complianceReport.coi_data.umbrella_limit || '---'}</span>
                    </div>
                    <div className="data-row">
                      <span className="label">ADD'L INSURED:</span>
                      <span className={`value ${complianceReport.coi_data.additional_insured_checked ? 'pass' : 'fail'}`}>
                        {complianceReport.coi_data.additional_insured_checked ? 'YES' : 'NO'}
                      </span>
                    </div>
                    <div className="data-row">
                      <span className="label">WAIVER SUB:</span>
                      <span className={`value ${complianceReport.coi_data.waiver_of_subrogation_checked ? 'pass' : 'fail'}`}>
                        {complianceReport.coi_data.waiver_of_subrogation_checked ? 'YES' : 'NO'}
                      </span>
                    </div>
                    <div className="data-row">
                      <span className="label">CG 20 10:</span>
                      <span className={`value ${complianceReport.coi_data.cg_20_10_endorsement ? 'pass' : ''}`}>
                        {complianceReport.coi_data.cg_20_10_endorsement ? 'YES' : 'NO'}
                      </span>
                    </div>
                    <div className="data-row">
                      <span className="label">CG 20 37:</span>
                      <span className={`value ${complianceReport.coi_data.cg_20_37_endorsement ? 'pass' : ''}`}>
                        {complianceReport.coi_data.cg_20_37_endorsement ? 'YES' : 'NO'}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {complianceTab === 'letter' && (
              <div className="letter-view">
                <div className="letter-content">
                  <pre>{complianceReport.fix_request_letter}</pre>
                </div>
                <button
                  className="pixel-btn secondary"
                  onClick={() => navigator.clipboard.writeText(complianceReport.fix_request_letter)}
                >
                  [COPY] COPY LETTER
                </button>
              </div>
            )}
          </section>
        )}

      </main>

      <footer className="footer">
        <p>* BROOKLYN NY *</p>
      </footer>
    </div>
  )
}

export default App
