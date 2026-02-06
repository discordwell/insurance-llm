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

interface ClassifyResult {
  document_type: 'coi' | 'lease' | 'gym' | 'timeshare' | 'influencer' | 'freelancer' | 'employment' | 'insurance_policy' | 'contract' | 'unknown'
  confidence: number
  description: string
  supported: boolean
}

interface InputSectionProps {
  getRootProps: () => Record<string, unknown>
  getInputProps: () => Record<string, unknown>
  isDragActive: boolean
  ocrLoading: boolean
  classifying: boolean
  loading: boolean
  uploadedFileName: string | null
  docType: ClassifyResult | null
  docText: string
  projectType: string
  selectedState: string
  setDocText: (text: string) => void
  setDocType: (type: ClassifyResult | null) => void
  setProjectType: (type: string) => void
  setSelectedState: (state: string) => void
  resetAll: () => void
  handleAnalyze: () => void
  getAnalyzeButtonText: () => string
}

export default function InputSection({
  getRootProps,
  getInputProps,
  isDragActive,
  ocrLoading,
  classifying,
  loading,
  uploadedFileName,
  docType,
  docText,
  projectType,
  selectedState,
  setDocText,
  setDocType,
  setProjectType,
  setSelectedState,
  resetAll,
  handleAnalyze,
  getAnalyzeButtonText,
}: InputSectionProps) {
  return (
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

      {docType?.supported && (
        <div className="options-row">
          {docType?.document_type === 'coi' && (
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
          )}

          {['coi', 'lease', 'gym', 'employment', 'timeshare', 'insurance_policy'].includes(docType?.document_type || '') && (
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
          )}
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
  )
}
