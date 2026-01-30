import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import './App.css'

// API base URL - uses environment variable in production, localhost in dev
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8081'

// Document classification result
interface ClassifyResult {
  document_type: 'coi' | 'lease' | 'insurance_policy' | 'contract' | 'unknown'
  confidence: number
  description: string
  supported: boolean
}

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
  'AZ': { mitigation: ['CG 24 26 endorsement', 'Higher primary limits on your own CGL'] },
  'CO': { mitigation: ['Wrap-up/OCIP for larger projects', 'Contractual liability coverage'] },
  'GA': { mitigation: ['Primary & non-contributory language still valid', 'Ensure adequate CGL limits'] },
  'KS': { mitigation: ['Wrap-up programs', 'Higher umbrella limits'] },
  'MT': { mitigation: ['OCIP/CCIP wrap-up insurance', 'Your own policy must be primary'] },
  'OR': { mitigation: ['CG 24 26 amendment endorsement', 'Contractual liability on your CGL'] },
}

// Friendly names for unsupported document types
const UNSUPPORTED_DOC_NAMES: Record<string, string> = {
  'insurance_policy': 'full insurance policies',
  'contract': 'general contracts',
  'unknown': 'this type of document',
}


function App() {
  const [loading, setLoading] = useState(false)
  const [ocrLoading, setOcrLoading] = useState(false)
  const [classifying, setClassifying] = useState(false)
  const [scanLines] = useState(true)
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null)

  // Document state
  const [docText, setDocText] = useState('')
  const [docType, setDocType] = useState<ClassifyResult | null>(null)
  const [projectType, setProjectType] = useState('commercial_construction')
  const [selectedState, setSelectedState] = useState('')

  // Results
  const [complianceReport, setComplianceReport] = useState<ComplianceReport | null>(null)
  const [complianceTab, setComplianceTab] = useState<'report' | 'letter'>('report')

  // Unsupported document modal
  const [showUnsupportedModal, setShowUnsupportedModal] = useState(false)
  const [unsupportedType, setUnsupportedType] = useState('')
  const [waitlistEmail, setWaitlistEmail] = useState('')
  const [emailSubmitted, setEmailSubmitted] = useState(false)

  const classifyDocument = async (text: string): Promise<ClassifyResult | null> => {
    setClassifying(true)
    try {
      const res = await fetch(`${API_BASE}/api/classify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text })
      })
      if (!res.ok) throw new Error('Classification failed')
      return await res.json()
    } catch (err) {
      console.error(err)
      return null
    } finally {
      setClassifying(false)
    }
  }

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    const file = acceptedFiles[0]
    if (!file) return

    setUploadedFileName(file.name)
    setComplianceReport(null)
    setDocType(null)

    let text = ''

    // For text files, read directly
    if (file.type === 'text/plain') {
      const reader = new FileReader()
      reader.onload = async () => {
        text = reader.result as string
        setDocText(text)
        // Classify after getting text
        const classification = await classifyDocument(text)
        handleClassification(classification)
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
      text = data.text
      setDocText(text)

      // Classify after OCR
      const classification = await classifyDocument(text)
      handleClassification(classification)
    } catch (err) {
      console.error(err)
      alert('Failed to process file. Make sure the backend is running!')
    } finally {
      setOcrLoading(false)
    }
  }, [])

  const handleClassification = (classification: ClassifyResult | null) => {
    if (!classification) {
      setDocType({ document_type: 'unknown', confidence: 0, description: 'Unknown', supported: false })
      setUnsupportedType('unknown')
      setShowUnsupportedModal(true)
      return
    }

    setDocType(classification)

    if (!classification.supported) {
      setUnsupportedType(classification.document_type)
      setShowUnsupportedModal(true)
    }
  }

  const fileToBase64 = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.readAsDataURL(file)
      reader.onload = () => {
        const result = reader.result as string
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

  const handleAnalyze = async () => {
    if (!docText.trim()) return

    // If no classification yet, classify first
    if (!docType) {
      const classification = await classifyDocument(docText)
      handleClassification(classification)
      if (!classification?.supported) return
      setDocType(classification)
    }

    // Route to appropriate analyzer
    if (docType?.document_type === 'coi') {
      await analyzeCOI()
    } else if (docType?.document_type === 'lease') {
      await analyzeLease()
    }
  }

  const analyzeCOI = async () => {
    setLoading(true)
    setComplianceReport(null)

    try {
      const res = await fetch(`${API_BASE}/api/check-coi-compliance`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          coi_text: docText,
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

  const analyzeLease = async () => {
    // TODO: Implement lease analysis
    // For now, show a placeholder
    setLoading(true)
    setTimeout(() => {
      setLoading(false)
      alert('Lease analysis coming soon! The backend endpoint is being built.')
    }, 500)
  }

  const handleWaitlistSubmit = () => {
    // TODO: Actually submit to a backend/email service
    console.log('Waitlist signup:', waitlistEmail, 'for', unsupportedType)
    setEmailSubmitted(true)
  }

  const resetAll = () => {
    setUploadedFileName(null)
    setDocText('')
    setDocType(null)
    setComplianceReport(null)
    setShowUnsupportedModal(false)
    setWaitlistEmail('')
    setEmailSubmitted(false)
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

  const getAnalyzeButtonText = () => {
    if (loading) return '[ ANALYZING... ]'
    if (classifying) return '[ READING... ]'
    if (ocrLoading) return '[ EXTRACTING... ]'
    return '> CAN THEY FUCK ME?'
  }

  return (
    <div className={`app ${scanLines ? 'scanlines' : ''}`}>
      <header className="header">
        <div className="logo">
          <span className="logo-icon">&#9043;</span>
          <h1>Can They Fuck Me?</h1>
        </div>
        <p className="tagline">Upload your insurance policy, lease, or contract to see how it stacks up</p>
      </header>

      <main className="main">
        <section className="input-section">
          <div {...getRootProps()} className={`dropzone ${isDragActive ? 'active' : ''} ${ocrLoading || classifying ? 'processing' : ''}`}>
            <input {...getInputProps()} />
            <div className="dropzone-content">
              {ocrLoading ? (
                <>
                  <span className="dropzone-icon">[...]</span>
                  <p>EXTRACTING TEXT...</p>
                </>
              ) : classifying ? (
                <>
                  <span className="dropzone-icon">[?]</span>
                  <p>IDENTIFYING DOCUMENT...</p>
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
              {docType && (
                <span className="doc-type-badge" style={{
                  backgroundColor: docType.supported ? 'var(--pixel-green)' : 'var(--pixel-yellow)'
                }}>
                  {docType.description}
                </span>
              )}
              <button className="clear-btn" onClick={resetAll}>[X]</button>
            </div>
          )}

          <textarea
            className="doc-input"
            value={docText}
            onChange={(e) => { setDocText(e.target.value); setDocType(null); }}
            placeholder="...or paste text here"
            rows={8}
          />

          {docType?.document_type === 'coi' && (
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
          )}

          {docType?.document_type === 'coi' && AI_LIMITED_STATES[selectedState] && (
            <div className="state-warning">
              !! {selectedState} limits Additional Insured coverage for shared fault
            </div>
          )}

          <button
            className={`pixel-btn primary ${loading || classifying || ocrLoading ? 'loading' : ''}`}
            onClick={handleAnalyze}
            disabled={loading || classifying || ocrLoading || !docText.trim()}
          >
            {getAnalyzeButtonText()}
          </button>
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

      {/* Unsupported Document Modal */}
      {showUnsupportedModal && (
        <div className="modal-overlay" onClick={() => setShowUnsupportedModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <span className="modal-icon">[!]</span>
              <h2>COMING SOON</h2>
            </div>
            <div className="modal-content">
              {emailSubmitted ? (
                <>
                  <p className="modal-success">GOT IT!</p>
                  <p>We'll ping you at <strong>{waitlistEmail}</strong> when we add support for {UNSUPPORTED_DOC_NAMES[unsupportedType] || unsupportedType}.</p>
                  <button className="pixel-btn primary" onClick={resetAll}>
                    [OK] COOL
                  </button>
                </>
              ) : (
                <>
                  <p>Sorry... we haven't done our homework on <strong>{UNSUPPORTED_DOC_NAMES[unsupportedType] || unsupportedType}</strong>.</p>
                  <p>Yet.</p>
                  <p className="modal-cta">Drop your email and we'll ping you first thing:</p>
                  <input
                    type="email"
                    className="pixel-input"
                    placeholder="you@example.com"
                    value={waitlistEmail}
                    onChange={(e) => setWaitlistEmail(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && waitlistEmail && handleWaitlistSubmit()}
                  />
                  <div className="modal-buttons">
                    <button
                      className="pixel-btn primary"
                      onClick={handleWaitlistSubmit}
                      disabled={!waitlistEmail}
                    >
                      [NOTIFY ME]
                    </button>
                    <button className="pixel-btn secondary" onClick={() => setShowUnsupportedModal(false)}>
                      [NEVERMIND]
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      <footer className="footer">
        <p>* BROOKLYN NY *</p>
      </footer>
    </div>
  )
}

export default App
