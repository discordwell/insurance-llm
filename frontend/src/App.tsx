import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import './App.css'

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
      const res = await fetch('http://localhost:8081/api/extract', {
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
      const res = await fetch('http://localhost:8081/api/generate-proposal', {
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
        <button className="scanline-toggle" onClick={() => setScanLines(!scanLines)}>
          {scanLines ? '[x]' : '[ ]'} CRT
        </button>
      </header>

      <main className="main">
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

        {extracted && (
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
