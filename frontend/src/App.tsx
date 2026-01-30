import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import './App.css'

// API base URL - uses environment variable in production, localhost in dev
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8081'

interface Coverage {
  type: string
  limit: string
  deductible?: string
  notes?: string
}

interface ExtractedPolicy {
  insured_name?: string
  policy_number?: string
  carrier?: string
  effective_date?: string
  expiration_date?: string
  coverages: Coverage[]
  total_premium?: string
  exclusions: string[]
  special_conditions: string[]
  risk_score?: number
  compliance_issues: string[]
  summary?: string
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

interface ProjectType {
  name: string
  gl_per_occurrence: string
  gl_aggregate: string
  umbrella_required: boolean
  umbrella_minimum?: string
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

const SAMPLE_DOCS = [
  {
    name: "Messy COI Email",
    text: `fwd: insurance stuff

hey can u check this out? their coverage looks weird to me lol

---
CERTIFICATE OF LIABILITY INSURANCE
Insured: Artisanal Pickle Co LLC
Policy#: BOP-2024-88821
Carrier: Midwest Mutual Insurance
Eff: 1/15/24 - 1/15/25

GL: $1M per occ / $2M agg
Prod/Comp: $1M
Med Pay: $5k
Damage to Rented: $100k
deductible $2,500

also they have:
- Umbrella: $5M (policy UMB-441)
- Workers comp as required

exclusions: no coverage for fermentation explosions (weird right??)
special endorsement for food spoilage added 3/2024

premium total: $4,250/yr

let me know thx
-mike`
  },
  {
    name: "Scanned Quote PDF (OCR)",
    text: `COMMERCIAL PROPERTY QUOTE
=========================

Prepared for: Brooklyn Roasting Company
Date: November 12, 2024
Quote #: CPQ-2024-1182

PROPOSED COVERAGE:
------------------
Building Coverage.............$2,500,000
Business Personal Property....$750,000
Business Income..............$500,000
Equipment Breakdown...........$250,000

Deductible: $5,000 / $25,000 wind/hail

ANNUAL PREMIUM: $12,400

Coverage Notes:
* Agreed value endorsement included
* Ordinance & law 25%
* NO flood coverage - Zone X requires separate
* Coffee roasting equipment schedule attached

Quoted by: Hartford Commercial Lines
Valid thru: 12/15/2024

[signature illegible]`
  },
  {
    name: "Policy Renewal Notice",
    text: `*** RENEWAL NOTICE ***

Dear Valued Policyholder,

Your policy is due for renewal:

Named Insured: Fixie Bike Repair & Custom Frames
                dba "Spoke & Chain"
Policy Number: CGL-NY-2023-44891
Current Term: Feb 1 2024 to Feb 1 2025

RENEWAL TERM CHANGES:
- Premium increase: $3,200 -> $3,850 (+20%)
- General Liability limit: $1M/$2M (unchanged)
- Professional Liability: ADDING $500k sublimit (new)
- Tools & Equipment floater: $75,000

IMPORTANT: Your current product liability sublimit of $500,000
will be REDUCED to $250,000 unless you opt for enhanced
coverage (+$400/yr).

Deductible remains $1,000.

EXCLUSIONS ADDED THIS TERM:
- E-bike battery fires
- Carbon fiber frame defects over $10k

Please respond by January 15, 2025.

Questions? Call 1-800-555-BIKE

Underwritten by: Velocity Insurance Group`
  }
]

function App() {
  const [inputText, setInputText] = useState('')
  const [extracted, setExtracted] = useState<ExtractedPolicy | null>(null)
  const [proposal, setProposal] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [activeTab, setActiveTab] = useState<'extract' | 'proposal'>('extract')
  const [scanLines, setScanLines] = useState(true)

  // COI Compliance State
  const [appMode, setAppMode] = useState<'extract' | 'compliance'>('extract')
  const [coiText, setCoiText] = useState('')
  const [projectType, setProjectType] = useState('commercial_construction')
  const [selectedState, setSelectedState] = useState('')
  const [complianceReport, setComplianceReport] = useState<ComplianceReport | null>(null)
  const [complianceTab, setComplianceTab] = useState<'report' | 'letter'>('report')

  const onDrop = useCallback((acceptedFiles: File[]) => {
    const file = acceptedFiles[0]
    if (file) {
      const reader = new FileReader()
      reader.onload = () => {
        setInputText(reader.result as string)
      }
      reader.readAsText(file)
    }
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'text/plain': ['.txt'], 'text/csv': ['.csv'] }
  })

  const handleExtract = async () => {
    if (!inputText.trim()) return
    setLoading(true)
    setExtracted(null)
    setProposal(null)

    try {
      const res = await fetch(`${API_BASE}/api/extract`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: inputText })
      })

      if (!res.ok) throw new Error('Extraction failed')
      const data = await res.json()
      setExtracted(data)
      setActiveTab('extract')
    } catch (err) {
      console.error(err)
      alert('Failed to extract document. Make sure the backend is running!')
    } finally {
      setLoading(false)
    }
  }

  const handleGenerateProposal = async () => {
    if (!extracted) return
    setLoading(true)

    try {
      const res = await fetch(`${API_BASE}/api/generate-proposal`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(extracted)
      })

      if (!res.ok) throw new Error('Proposal generation failed')
      const data = await res.json()
      setProposal(data.proposal)
      setActiveTab('proposal')
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const loadSample = (sample: typeof SAMPLE_DOCS[0]) => {
    setInputText(sample.text)
    setExtracted(null)
    setProposal(null)
  }

  const loadCoiSample = (sample: typeof SAMPLE_COIS[0]) => {
    setCoiText(sample.text)
    setComplianceReport(null)
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

  const getRiskColor = (score?: number) => {
    if (!score) return 'var(--pixel-gray)'
    if (score >= 80) return 'var(--pixel-green)'
    if (score >= 60) return 'var(--pixel-yellow)'
    return 'var(--pixel-red)'
  }

  return (
    <div className={`app ${scanLines ? 'scanlines' : ''}`}>
      <header className="header">
        <div className="logo">
          <span className="logo-icon">&#9043;</span>
          <h1>INSURANCE.EXE</h1>
        </div>
        <p className="tagline">* messy docs to clean data * pixel perfect coverage analysis *</p>
        <div className="header-controls">
          <div className="mode-toggle">
            <button
              className={`mode-btn ${appMode === 'extract' ? 'active' : ''}`}
              onClick={() => setAppMode('extract')}
            >
              EXTRACT
            </button>
            <button
              className={`mode-btn ${appMode === 'compliance' ? 'active' : ''}`}
              onClick={() => setAppMode('compliance')}
            >
              COI CHECK
            </button>
          </div>
          <button className="scanline-toggle" onClick={() => setScanLines(!scanLines)}>
            {scanLines ? '[x]' : '[ ]'} CRT
          </button>
        </div>
      </header>

      <main className="main">
        {appMode === 'extract' && (
        <section className="input-section">
          <div className="section-header">
            <h2>&gt; INPUT DOCUMENT</h2>
            <span className="blink">_</span>
          </div>

          <div className="sample-docs">
            <span className="label">LOAD SAMPLE:</span>
            {SAMPLE_DOCS.map((doc, i) => (
              <button key={i} className="pixel-btn small" onClick={() => loadSample(doc)}>
                {doc.name}
              </button>
            ))}
          </div>

          <div {...getRootProps()} className={`dropzone ${isDragActive ? 'active' : ''}`}>
            <input {...getInputProps()} />
            <div className="dropzone-content">
              <span className="dropzone-icon">[FILE]</span>
              <p>{isDragActive ? 'DROP IT LIKE ITS HOT' : 'drag & drop .txt file here'}</p>
            </div>
          </div>

          <textarea
            className="doc-input"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder={`paste your messy insurance document here...\n\nCOIs, quotes, policy summaries, email forwards...\nwe'll make sense of it *`}
            rows={12}
          />

          <button
            className={`pixel-btn primary ${loading ? 'loading' : ''}`}
            onClick={handleExtract}
            disabled={loading || !inputText.trim()}
          >
            {loading ? '[ PROCESSING... ]' : '> EXTRACT DATA'}
          </button>
        </section>
        )}

        {appMode === 'compliance' && (
        <section className="input-section">
          <div className="section-header">
            <h2>&gt; COI COMPLIANCE CHECKER</h2>
            <span className="blink">_</span>
          </div>

          <div className="compliance-intro">
            <p className="warning-text">
              !! 70% of COIs are non-compliant on first submission. Missing endorsements cost $8,500+ per incident.
            </p>
            <p>
              Being listed as "Certificate Holder" does NOT make you an Additional Insured.
              This distinction has cost companies millions.
            </p>
          </div>

          <div className="sample-docs">
            <span className="label">SAMPLE COIs:</span>
            {SAMPLE_COIS.map((doc, i) => (
              <button key={i} className="pixel-btn small" onClick={() => loadCoiSample(doc)}>
                {doc.name}
              </button>
            ))}
          </div>

          <div className="project-type-selector">
            <span className="label">PROJECT TYPE:</span>
            <select
              className="pixel-select"
              value={projectType}
              onChange={(e) => setProjectType(e.target.value)}
            >
              <option value="commercial_construction">Commercial Construction ($1M/$2M GL)</option>
              <option value="residential_construction">Residential Construction ($500K/$1M GL)</option>
              <option value="government_municipal">Government/Municipal ($2M/$4M GL)</option>
              <option value="industrial_manufacturing">Industrial/Manufacturing ($2M/$4M GL)</option>
            </select>
          </div>

          <div className="state-selector">
            <span className="label">PROJECT STATE:</span>
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
            {AI_LIMITED_STATES[selectedState] && (
              <div className="state-note">
                <span className="note-header">{selectedState} AI Coverage Note:</span>
                <span className="note-text">Broad anti-indemnity statute limits AI for shared fault.</span>
                <div className="mitigation-list">
                  <span className="mitigation-header">Mitigation options:</span>
                  {AI_LIMITED_STATES[selectedState].mitigation.map((m, i) => (
                    <span key={i} className="mitigation-item">• {m}</span>
                  ))}
                </div>
              </div>
            )}
          </div>

          <textarea
            className="doc-input"
            value={coiText}
            onChange={(e) => setCoiText(e.target.value)}
            placeholder={`Paste Certificate of Insurance (ACORD 25) here...

Look for:
- General Liability limits
- Additional Insured checkbox
- Waiver of Subrogation checkbox
- CG 20 10 / CG 20 37 endorsements
- Certificate Holder section`}
            rows={14}
          />

          <button
            className={`pixel-btn primary ${loading ? 'loading' : ''}`}
            onClick={handleCheckCompliance}
            disabled={loading || !coiText.trim()}
          >
            {loading ? '[ ANALYZING... ]' : '> CHECK COMPLIANCE'}
          </button>
        </section>
        )}

        {complianceReport && appMode === 'compliance' && (
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

        {extracted && appMode === 'extract' && (
          <section className="output-section">
            <div className="tabs">
              <button
                className={`tab ${activeTab === 'extract' ? 'active' : ''}`}
                onClick={() => setActiveTab('extract')}
              >
                * EXTRACTED DATA
              </button>
              <button
                className={`tab ${activeTab === 'proposal' ? 'active' : ''}`}
                onClick={() => setActiveTab('proposal')}
              >
                * PROPOSAL
              </button>
            </div>

            {activeTab === 'extract' && (
              <div className="extracted-data">
                <div className="data-grid">
                  <div className="data-card">
                    <h3>POLICY INFO</h3>
                    <div className="data-row">
                      <span className="label">INSURED:</span>
                      <span className="value">{extracted.insured_name || '---'}</span>
                    </div>
                    <div className="data-row">
                      <span className="label">POLICY #:</span>
                      <span className="value mono">{extracted.policy_number || '---'}</span>
                    </div>
                    <div className="data-row">
                      <span className="label">CARRIER:</span>
                      <span className="value">{extracted.carrier || '---'}</span>
                    </div>
                    <div className="data-row">
                      <span className="label">TERM:</span>
                      <span className="value">
                        {extracted.effective_date || '?'} -&gt; {extracted.expiration_date || '?'}
                      </span>
                    </div>
                    <div className="data-row">
                      <span className="label">PREMIUM:</span>
                      <span className="value highlight">{extracted.total_premium || '---'}</span>
                    </div>
                  </div>

                  <div className="data-card">
                    <h3>RISK SCORE</h3>
                    <div className="risk-meter">
                      <div
                        className="risk-fill"
                        style={{
                          width: `${extracted.risk_score || 0}%`,
                          backgroundColor: getRiskColor(extracted.risk_score)
                        }}
                      />
                      <span className="risk-value">{extracted.risk_score || '?'}/100</span>
                    </div>
                    <p className="risk-label">
                      {extracted.risk_score && extracted.risk_score >= 80 ? 'EXCELLENT COVERAGE' :
                       extracted.risk_score && extracted.risk_score >= 60 ? 'ADEQUATE COVERAGE' :
                       'COVERAGE GAPS DETECTED'}
                    </p>
                  </div>
                </div>

                {extracted.coverages.length > 0 && (
                  <div className="data-card full-width">
                    <h3>* COVERAGES</h3>
                    <table className="pixel-table">
                      <thead>
                        <tr>
                          <th>TYPE</th>
                          <th>LIMIT</th>
                          <th>DEDUCTIBLE</th>
                          <th>NOTES</th>
                        </tr>
                      </thead>
                      <tbody>
                        {extracted.coverages.map((cov, i) => (
                          <tr key={i}>
                            <td>{cov.type}</td>
                            <td className="mono">{cov.limit}</td>
                            <td className="mono">{cov.deductible || '---'}</td>
                            <td className="notes">{cov.notes || '---'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {extracted.exclusions.length > 0 && (
                  <div className="data-card warning">
                    <h3>!! EXCLUSIONS</h3>
                    <ul className="pixel-list">
                      {extracted.exclusions.map((ex, i) => (
                        <li key={i}>{ex}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {extracted.compliance_issues.length > 0 && (
                  <div className="data-card danger">
                    <h3>XX COMPLIANCE ISSUES</h3>
                    <ul className="pixel-list">
                      {extracted.compliance_issues.map((issue, i) => (
                        <li key={i}>{issue}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {extracted.summary && (
                  <div className="data-card">
                    <h3>* SUMMARY</h3>
                    <p className="summary-text">{extracted.summary}</p>
                  </div>
                )}

                <button
                  className={`pixel-btn secondary ${loading ? 'loading' : ''}`}
                  onClick={handleGenerateProposal}
                  disabled={loading}
                >
                  {loading ? '[ GENERATING... ]' : '> GENERATE CLIENT PROPOSAL'}
                </button>
              </div>
            )}

            {activeTab === 'proposal' && proposal && (
              <div className="proposal-view">
                <div className="proposal-content">
                  <pre>{proposal}</pre>
                </div>
                <button
                  className="pixel-btn secondary"
                  onClick={() => navigator.clipboard.writeText(proposal)}
                >
                  [COPY] COPY TO CLIPBOARD
                </button>
              </div>
            )}
          </section>
        )}
      </main>

      <footer className="footer">
        <p>* INSURANCE.EXE v1.0 * BROOKLYN NY * 2015 NEVER DIED *</p>
        <p className="credits">built for FULCRUM TECH * messy to polished in minutes</p>
      </footer>
    </div>
  )
}

export default App
