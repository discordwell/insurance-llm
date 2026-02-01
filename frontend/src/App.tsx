import { useState, useCallback, useEffect } from 'react'
import { useDropzone } from 'react-dropzone'
import './App.css'
import { getOffersForDocType } from './config/affiliates'
import type { AffiliateOffer } from './config/affiliates'
import { STRIPE_DONATION_LINK } from './config/stripe'

// API base URL - uses environment variable in production, localhost in dev
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8081'

// Document classification result
interface ClassifyResult {
  document_type: 'coi' | 'lease' | 'gym' | 'timeshare' | 'influencer' | 'freelancer' | 'employment' | 'insurance_policy' | 'contract' | 'unknown'
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

// Extraction confidence metadata
interface ExtractionMetadata {
  overall_confidence: number  // 0-1
  needs_human_review: boolean
  review_reasons: string[]
  low_confidence_fields: string[]
  extraction_notes?: string
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

// Lease Analysis Types
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

// Generic RedFlag type used by new contract types
interface ContractRedFlag {
  name: string
  severity: 'critical' | 'warning' | 'info'
  clause_text?: string
  explanation: string
  protection: string
}

// Gym Contract Types
interface GymContractReport {
  overall_risk: string
  risk_score: number
  gym_name?: string
  contract_type: string
  monthly_fee?: string
  cancellation_difficulty: string
  red_flags: ContractRedFlag[]
  state_protections: string[]
  summary: string
  cancellation_guide: string
}

// Employment Contract Types
interface EmploymentContractReport {
  overall_risk: string
  risk_score: number
  document_type: string
  has_non_compete: boolean
  non_compete_enforceable?: string
  has_arbitration: boolean
  has_ip_assignment: boolean
  red_flags: ContractRedFlag[]
  state_notes: string[]
  summary: string
  negotiation_points: string
}

// Freelancer Contract Types
interface FreelancerContractReport {
  overall_risk: string
  risk_score: number
  contract_type: string
  payment_terms?: string
  ip_ownership: string
  has_kill_fee: boolean
  revision_limit?: string
  red_flags: ContractRedFlag[]
  missing_protections: string[]
  summary: string
  suggested_changes: string
}

// Influencer Contract Types
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

// Timeshare Contract Types
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

// Insurance Policy Types (with different protection field name)
interface InsurancePolicyRedFlag {
  name: string
  severity: 'critical' | 'warning' | 'info'
  clause_text?: string
  explanation: string
  what_to_ask: string
}

interface InsurancePolicyReport {
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
  'contract': 'general contracts (try uploading a specific contract type)',
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
  const [leaseReport, setLeaseReport] = useState<LeaseAnalysisReport | null>(null)
  const [leaseTab, setLeaseTab] = useState<'report' | 'letter'>('report')
  const [gymReport, setGymReport] = useState<GymContractReport | null>(null)
  const [gymTab, setGymTab] = useState<'report' | 'letter'>('report')
  const [employmentReport, setEmploymentReport] = useState<EmploymentContractReport | null>(null)
  const [employmentTab, setEmploymentTab] = useState<'report' | 'letter'>('report')
  const [freelancerReport, setFreelancerReport] = useState<FreelancerContractReport | null>(null)
  const [freelancerTab, setFreelancerTab] = useState<'report' | 'letter'>('report')
  const [influencerReport, setInfluencerReport] = useState<InfluencerContractReport | null>(null)
  const [influencerTab, setInfluencerTab] = useState<'report' | 'letter'>('report')
  const [timeshareReport, setTimeshareReport] = useState<TimeshareContractReport | null>(null)
  const [timeshareTab, setTimeshareTab] = useState<'report' | 'letter'>('report')
  const [insurancePolicyReport, setInsurancePolicyReport] = useState<InsurancePolicyReport | null>(null)
  const [insurancePolicyTab, setInsurancePolicyTab] = useState<'report' | 'letter'>('report')

  // Unsupported document modal
  const [showUnsupportedModal, setShowUnsupportedModal] = useState(false)
  const [unsupportedType, setUnsupportedType] = useState('')
  const [waitlistEmail, setWaitlistEmail] = useState('')
  const [emailSubmitted, setEmailSubmitted] = useState(false)

  // Disclaimer modal
  const [showDisclaimerModal, setShowDisclaimerModal] = useState(false)
  const [disclaimerInput, setDisclaimerInput] = useState('')
  const [disclaimerAccepted, setDisclaimerAccepted] = useState(false)
  const [pendingAnalysis, setPendingAnalysis] = useState<'coi' | 'lease' | 'gym' | 'employment' | 'freelancer' | 'influencer' | 'timeshare' | 'insurance_policy' | null>(null)

  // Auth state
  const [isLoggedIn, setIsLoggedIn] = useState(false)
  const [userEmail, setUserEmail] = useState<string | null>(null)
  const [authToken, setAuthToken] = useState<string | null>(() => localStorage.getItem('auth_token'))
  const [showAuthModal, setShowAuthModal] = useState(false)
  const [authMode, setAuthMode] = useState<'login' | 'signup'>('signup')
  const [authEmail, setAuthEmail] = useState('')
  const [authPassword, setAuthPassword] = useState('')
  const [authError, setAuthError] = useState<string | null>(null)
  const [authLoading, setAuthLoading] = useState(false)

  // History state
  const [showHistoryModal, setShowHistoryModal] = useState(false)
  const [userHistory, setUserHistory] = useState<Array<{
    id: number
    created_at: string
    document_type: string
    overall_risk: string
    risk_score: number
  }>>([])
  const [historyLoading, setHistoryLoading] = useState(false)

  // Affiliate offer state
  const [currentOffer, setCurrentOffer] = useState<AffiliateOffer | null>(null)
  const [, setOfferIndex] = useState(0)

  // Donation link text - randomized on mount
  const donationTexts = [
    { text: 'Support my <s>caffeine</s> Claude addiction', isHtml: true },
    { text: 'Compute is cheap / but it ain\'t free / if this helped you out / then please pay me', isHtml: false },
    { text: 'Feed the AI overlords', isHtml: false },
    { text: 'This site costs mass/energy, pls donate', isHtml: false },
    { text: 'Buy me mass-energy equivalence (E=mc²)', isHtml: false },
    { text: 'Tokens aren\'t free, help a dev out', isHtml: false },
    { text: 'GPU go brrrr (but it costs $$$)', isHtml: false },
  ]
  const [donationText] = useState(() => donationTexts[Math.floor(Math.random() * donationTexts.length)])

  // Check auth status on mount
  useEffect(() => {
    const checkAuth = async () => {
      if (!authToken) return

      try {
        const res = await fetch(`${API_BASE}/api/auth/me`, {
          headers: { 'Authorization': `Bearer ${authToken}` }
        })
        const data = await res.json()
        if (data.authenticated) {
          setIsLoggedIn(true)
          setUserEmail(data.user.email)
        } else {
          // Token invalid, clear it
          localStorage.removeItem('auth_token')
          setAuthToken(null)
        }
      } catch (err) {
        console.error('Auth check failed:', err)
      }
    }
    checkAuth()
  }, [authToken])

  // Rotate affiliate offers during loading
  useEffect(() => {
    if (!loading || !docType) return

    const offers = getOffersForDocType(docType.document_type)
    if (offers.length === 0) return

    setCurrentOffer(offers[0])
    setOfferIndex(0)

    const interval = setInterval(() => {
      setOfferIndex(prev => {
        const next = (prev + 1) % offers.length
        setCurrentOffer(offers[next])
        return next
      })
    }, 5000)

    return () => clearInterval(interval)
  }, [loading, docType])

  // Auth functions
  const handleSignup = async () => {
    setAuthError(null)
    setAuthLoading(true)

    try {
      const res = await fetch(`${API_BASE}/api/auth/signup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: authEmail, password: authPassword })
      })

      const data = await res.json()

      if (!res.ok) {
        throw new Error(data.detail || 'Signup failed')
      }

      // Save token and update state
      localStorage.setItem('auth_token', data.token)
      setAuthToken(data.token)
      setIsLoggedIn(true)
      setUserEmail(data.user.email)
      setShowAuthModal(false)
      setAuthEmail('')
      setAuthPassword('')
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Signup failed'
      setAuthError(errorMessage)
    } finally {
      setAuthLoading(false)
    }
  }

  const handleLogin = async () => {
    setAuthError(null)
    setAuthLoading(true)

    try {
      const res = await fetch(`${API_BASE}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: authEmail, password: authPassword })
      })

      const data = await res.json()

      if (!res.ok) {
        throw new Error(data.detail || 'Login failed')
      }

      // Save token and update state
      localStorage.setItem('auth_token', data.token)
      setAuthToken(data.token)
      setIsLoggedIn(true)
      setUserEmail(data.user.email)
      setShowAuthModal(false)
      setAuthEmail('')
      setAuthPassword('')
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Login failed'
      setAuthError(errorMessage)
    } finally {
      setAuthLoading(false)
    }
  }

  const handleLogout = async () => {
    try {
      await fetch(`${API_BASE}/api/auth/logout`, {
        method: 'POST',
        headers: authToken ? { 'Authorization': `Bearer ${authToken}` } : {}
      })
    } catch (err) {
      console.error('Logout error:', err)
    }

    localStorage.removeItem('auth_token')
    setAuthToken(null)
    setIsLoggedIn(false)
    setUserEmail(null)
    setUserHistory([])
  }

  // Fetch user history
  const fetchHistory = async () => {
    if (!authToken) return

    setHistoryLoading(true)
    try {
      const res = await fetch(`${API_BASE}/api/user/history`, {
        headers: { 'Authorization': `Bearer ${authToken}` }
      })
      if (res.ok) {
        const data = await res.json()
        setUserHistory(data.uploads || [])
      }
    } catch (err) {
      console.error('Failed to fetch history:', err)
    } finally {
      setHistoryLoading(false)
    }
  }

  // Fetch history when modal opens
  const openHistoryModal = () => {
    setShowHistoryModal(true)
    fetchHistory()
  }

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
    setLeaseReport(null)
    setGymReport(null)
    setEmploymentReport(null)
    setFreelancerReport(null)
    setInfluencerReport(null)
    setTimeshareReport(null)
    setInsurancePolicyReport(null)
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
    let currentDocType = docType
    if (!currentDocType) {
      const classification = await classifyDocument(docText)
      handleClassification(classification)
      if (!classification?.supported) return
      setDocType(classification)
      currentDocType = classification
    }

    // If disclaimer not yet accepted, show the modal
    if (!disclaimerAccepted) {
      const docTypeStr = currentDocType?.document_type
      if (docTypeStr && ['coi', 'lease', 'gym', 'employment', 'freelancer', 'influencer', 'timeshare', 'insurance_policy'].includes(docTypeStr)) {
        setPendingAnalysis(docTypeStr as typeof pendingAnalysis)
      }
      setShowDisclaimerModal(true)
      setDisclaimerInput('')
      return
    }

    // Route to appropriate analyzer
    await runAnalysis(currentDocType?.document_type)
  }

  const runAnalysis = async (docTypeStr: string | undefined) => {
    switch (docTypeStr) {
      case 'coi':
        await analyzeCOI()
        break
      case 'lease':
        await analyzeLease()
        break
      case 'gym':
        await analyzeGym()
        break
      case 'employment':
        await analyzeEmployment()
        break
      case 'freelancer':
        await analyzeFreelancer()
        break
      case 'influencer':
        await analyzeInfluencer()
        break
      case 'timeshare':
        await analyzeTimeshare()
        break
      case 'insurance_policy':
        await analyzeInsurancePolicy()
        break
    }
  }

  const handleDisclaimerSubmit = async () => {
    if (disclaimerInput.toLowerCase().trim() === 'not legal advice') {
      setDisclaimerAccepted(true)
      setShowDisclaimerModal(false)

      // Run the pending analysis
      if (pendingAnalysis) {
        await runAnalysis(pendingAnalysis)
      }
      setPendingAnalysis(null)
    }
  }

  const handleDisclaimerCancel = () => {
    setShowDisclaimerModal(false)
    setPendingAnalysis(null)
    // Don't set disclaimerAccepted - they can try again
  }

  const analyzeCOI = async () => {
    setLoading(true)
    setComplianceReport(null)

    try {
      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      if (authToken) {
        headers['Authorization'] = `Bearer ${authToken}`
      }

      const res = await fetch(`${API_BASE}/api/check-coi-compliance`, {
        method: 'POST',
        headers,
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
    setLoading(true)
    setLeaseReport(null)

    try {
      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      if (authToken) {
        headers['Authorization'] = `Bearer ${authToken}`
      }

      const res = await fetch(`${API_BASE}/api/analyze-lease`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          lease_text: docText,
          state: selectedState || null,
          lease_type: 'commercial'
        })
      })

      if (!res.ok) throw new Error('Lease analysis failed')
      const data = await res.json()
      setLeaseReport(data)
      setLeaseTab('report')
    } catch (err) {
      console.error(err)
      alert('Failed to analyze lease. Make sure the backend is running!')
    } finally {
      setLoading(false)
    }
  }

  const analyzeGym = async () => {
    setLoading(true)
    setGymReport(null)

    try {
      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      if (authToken) {
        headers['Authorization'] = `Bearer ${authToken}`
      }

      const res = await fetch(`${API_BASE}/api/analyze-gym`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          contract_text: docText,
          state: selectedState || null
        })
      })

      if (!res.ok) throw new Error('Gym contract analysis failed')
      const data = await res.json()
      setGymReport(data)
      setGymTab('report')
    } catch (err) {
      console.error(err)
      alert('Failed to analyze gym contract. Make sure the backend is running!')
    } finally {
      setLoading(false)
    }
  }

  const analyzeEmployment = async () => {
    setLoading(true)
    setEmploymentReport(null)

    try {
      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      if (authToken) {
        headers['Authorization'] = `Bearer ${authToken}`
      }

      const res = await fetch(`${API_BASE}/api/analyze-employment`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          contract_text: docText,
          state: selectedState || null
        })
      })

      if (!res.ok) throw new Error('Employment contract analysis failed')
      const data = await res.json()
      setEmploymentReport(data)
      setEmploymentTab('report')
    } catch (err) {
      console.error(err)
      alert('Failed to analyze employment contract. Make sure the backend is running!')
    } finally {
      setLoading(false)
    }
  }

  const analyzeFreelancer = async () => {
    setLoading(true)
    setFreelancerReport(null)

    try {
      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      if (authToken) {
        headers['Authorization'] = `Bearer ${authToken}`
      }

      const res = await fetch(`${API_BASE}/api/analyze-freelancer`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          contract_text: docText
        })
      })

      if (!res.ok) throw new Error('Freelancer contract analysis failed')
      const data = await res.json()
      setFreelancerReport(data)
      setFreelancerTab('report')
    } catch (err) {
      console.error(err)
      alert('Failed to analyze freelancer contract. Make sure the backend is running!')
    } finally {
      setLoading(false)
    }
  }

  const analyzeInfluencer = async () => {
    setLoading(true)
    setInfluencerReport(null)

    try {
      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      if (authToken) {
        headers['Authorization'] = `Bearer ${authToken}`
      }

      const res = await fetch(`${API_BASE}/api/analyze-influencer`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          contract_text: docText
        })
      })

      if (!res.ok) throw new Error('Influencer contract analysis failed')
      const data = await res.json()
      setInfluencerReport(data)
      setInfluencerTab('report')
    } catch (err) {
      console.error(err)
      alert('Failed to analyze influencer contract. Make sure the backend is running!')
    } finally {
      setLoading(false)
    }
  }

  const analyzeTimeshare = async () => {
    setLoading(true)
    setTimeshareReport(null)

    try {
      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      if (authToken) {
        headers['Authorization'] = `Bearer ${authToken}`
      }

      const res = await fetch(`${API_BASE}/api/analyze-timeshare`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          contract_text: docText,
          state: selectedState || null
        })
      })

      if (!res.ok) throw new Error('Timeshare contract analysis failed')
      const data = await res.json()
      setTimeshareReport(data)
      setTimeshareTab('report')
    } catch (err) {
      console.error(err)
      alert('Failed to analyze timeshare contract. Make sure the backend is running!')
    } finally {
      setLoading(false)
    }
  }

  const analyzeInsurancePolicy = async () => {
    setLoading(true)
    setInsurancePolicyReport(null)

    try {
      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      if (authToken) {
        headers['Authorization'] = `Bearer ${authToken}`
      }

      const res = await fetch(`${API_BASE}/api/analyze-insurance-policy`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          policy_text: docText,
          state: selectedState || null
        })
      })

      if (!res.ok) throw new Error('Insurance policy analysis failed')
      const data = await res.json()
      setInsurancePolicyReport(data)
      setInsurancePolicyTab('report')
    } catch (err) {
      console.error(err)
      alert('Failed to analyze insurance policy. Make sure the backend is running!')
    } finally {
      setLoading(false)
    }
  }

  const handleWaitlistSubmit = async () => {
    try {
      await fetch(`${API_BASE}/api/waitlist`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: waitlistEmail,
          document_type: unsupportedType,
          document_text: docText
        })
      })
    } catch (err) {
      console.error('Waitlist signup failed:', err)
    }
    setEmailSubmitted(true)
  }

  const resetAll = () => {
    setUploadedFileName(null)
    setDocText('')
    setDocType(null)
    setComplianceReport(null)
    setLeaseReport(null)
    setGymReport(null)
    setEmploymentReport(null)
    setFreelancerReport(null)
    setInfluencerReport(null)
    setTimeshareReport(null)
    setInsurancePolicyReport(null)
    setShowUnsupportedModal(false)
    setWaitlistEmail('')
    setEmailSubmitted(false)
    setDisclaimerAccepted(false)
    setDisclaimerInput('')
    setPendingAnalysis(null)
    setCurrentOffer(null)
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

  const getRiskColor = (risk: string) => {
    switch (risk) {
      case 'high':
      case 'critical':
        return 'var(--pixel-red)'
      case 'medium':
      case 'warning':
        return 'var(--pixel-yellow)'
      case 'low':
      case 'info':
        return 'var(--pixel-green)'
      default:
        return 'var(--pixel-gray)'
    }
  }

  const getRiskLabel = (risk: string) => {
    switch (risk) {
      case 'high':
        return 'HIGH RISK'
      case 'medium':
        return 'MEDIUM RISK'
      case 'low':
        return 'LOW RISK'
      default:
        return risk.toUpperCase()
    }
  }

  return (
    <div className={`app ${scanLines ? 'scanlines' : ''}`}>
      <header className="header">
        <div className="header-row">
          <div className="logo">
            <span className="logo-icon">&#9043;</span>
            <h1>Can They Fuck Me?</h1>
          </div>
          <div className="auth-section">
            {isLoggedIn ? (
              <>
                <span className="user-email">{userEmail}</span>
                <button className="auth-btn" onClick={openHistoryModal}>History</button>
                <button className="auth-btn logout-btn" onClick={handleLogout}>Log Out</button>
              </>
            ) : (
              <button className="auth-btn signup-btn" onClick={() => { setAuthMode('signup'); setShowAuthModal(true) }}>
                Sign In to Save History
              </button>
            )}
          </div>
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

            {/* Confidence Banner */}
            {complianceReport.extraction_metadata && (
              <div className={`confidence-banner ${complianceReport.extraction_metadata.needs_human_review ? 'needs-review' : 'confident'}`}>
                <div className="confidence-header">
                  <span className="confidence-icon">
                    {complianceReport.extraction_metadata.needs_human_review ? '[?]' : '[✓]'}
                  </span>
                  <span className="confidence-label">EXTRACTION CONFIDENCE:</span>
                  <span className={`confidence-value ${complianceReport.extraction_metadata.overall_confidence >= 0.8 ? 'high' : complianceReport.extraction_metadata.overall_confidence >= 0.6 ? 'medium' : 'low'}`}>
                    {Math.round(complianceReport.extraction_metadata.overall_confidence * 100)}%
                  </span>
                </div>
                {complianceReport.extraction_metadata.needs_human_review && (
                  <div className="review-warning">
                    <span className="warning-text">HUMAN REVIEW RECOMMENDED</span>
                    {complianceReport.extraction_metadata.review_reasons.length > 0 && (
                      <ul className="review-reasons">
                        {complianceReport.extraction_metadata.review_reasons.slice(0, 3).map((reason, i) => (
                          <li key={i}>{reason}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
                {complianceReport.extraction_metadata.low_confidence_fields.length > 0 && (
                  <div className="low-confidence-fields">
                    <span className="label">LOW CONFIDENCE:</span>
                    {complianceReport.extraction_metadata.low_confidence_fields.map((field, i) => (
                      <span key={i} className="field-badge">{field.replace(/_/g, ' ')}</span>
                    ))}
                  </div>
                )}
              </div>
            )}

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

        {/* Lease Analysis Results */}
        {leaseReport && (
          <section className="output-section lease-output">
            <div className="compliance-header">
              <div
                className="compliance-status-badge"
                style={{ backgroundColor: getRiskColor(leaseReport.overall_risk) }}
              >
                {getRiskLabel(leaseReport.overall_risk)}
              </div>
              <div className="risk-exposure">
                <span className="label">RISK SCORE:</span>
                <span className="value">{leaseReport.risk_score}/100</span>
              </div>
            </div>

            <p className="summary-text">{leaseReport.summary}</p>

            <div className="tabs">
              <button
                className={`tab ${leaseTab === 'report' ? 'active' : ''}`}
                onClick={() => setLeaseTab('report')}
              >
                * ANALYSIS
              </button>
              <button
                className={`tab ${leaseTab === 'letter' ? 'active' : ''}`}
                onClick={() => setLeaseTab('letter')}
              >
                * NEGOTIATION LETTER
              </button>
            </div>

            {leaseTab === 'report' && (
              <div className="compliance-report">
                {/* Red Flags */}
                {leaseReport.red_flags.filter(rf => rf.severity === 'critical').length > 0 && (
                  <div className="data-card danger full-width">
                    <h3>XX CRITICAL RED FLAGS</h3>
                    <div className="compliance-items">
                      {leaseReport.red_flags.filter(rf => rf.severity === 'critical').map((flag, i) => (
                        <div key={i} className="compliance-item fail">
                          <div className="item-header">
                            <span className="status-icon">✗</span>
                            <span className="item-name">{flag.name}</span>
                          </div>
                          {flag.clause_text && (
                            <div className="clause-text">
                              <span className="label">CLAUSE:</span>
                              <span className="value">"{flag.clause_text}"</span>
                            </div>
                          )}
                          <p className="item-explanation">{flag.explanation}</p>
                          <div className="protection-box">
                            <span className="label">PROTECTION:</span>
                            <span className="value">{flag.protection}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Warnings */}
                {leaseReport.red_flags.filter(rf => rf.severity === 'warning').length > 0 && (
                  <div className="data-card warning full-width">
                    <h3>!! WATCH OUT FOR</h3>
                    <div className="compliance-items">
                      {leaseReport.red_flags.filter(rf => rf.severity === 'warning').map((flag, i) => (
                        <div key={i} className="compliance-item warning">
                          <div className="item-header">
                            <span className="status-icon">!</span>
                            <span className="item-name">{flag.name}</span>
                          </div>
                          {flag.clause_text && (
                            <div className="clause-text">
                              <span className="label">CLAUSE:</span>
                              <span className="value">"{flag.clause_text}"</span>
                            </div>
                          )}
                          <p className="item-explanation">{flag.explanation}</p>
                          <div className="protection-box">
                            <span className="label">PROTECTION:</span>
                            <span className="value">{flag.protection}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Missing Protections */}
                {leaseReport.missing_protections.length > 0 && (
                  <div className="data-card info full-width">
                    <h3>?? MISSING PROTECTIONS</h3>
                    <div className="missing-list">
                      {leaseReport.missing_protections.map((item, i) => (
                        <div key={i} className="missing-item">
                          <span className="status-icon">-</span>
                          <span>{item}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Insurance Requirements Found */}
                {leaseReport.insurance_requirements.length > 0 && (
                  <div className="data-card full-width">
                    <h3>* INSURANCE REQUIREMENTS</h3>
                    <div className="compliance-items">
                      {leaseReport.insurance_requirements.map((req, i) => (
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
                      <span className="value">{leaseReport.lease_type?.toUpperCase() || '---'}</span>
                    </div>
                    <div className="data-row">
                      <span className="label">LANDLORD:</span>
                      <span className="value">{leaseReport.landlord_name || '---'}</span>
                    </div>
                    <div className="data-row">
                      <span className="label">TENANT:</span>
                      <span className="value">{leaseReport.tenant_name || '---'}</span>
                    </div>
                    <div className="data-row">
                      <span className="label">PROPERTY:</span>
                      <span className="value">{leaseReport.property_address || '---'}</span>
                    </div>
                    <div className="data-row">
                      <span className="label">TERM:</span>
                      <span className="value">{leaseReport.lease_term || '---'}</span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {leaseTab === 'letter' && (
              <div className="letter-view">
                <div className="letter-content">
                  <pre>{leaseReport.negotiation_letter}</pre>
                </div>
                <button
                  className="pixel-btn secondary"
                  onClick={() => navigator.clipboard.writeText(leaseReport.negotiation_letter)}
                >
                  [COPY] COPY LETTER
                </button>
              </div>
            )}
          </section>
        )}

        {/* Gym Contract Results */}
        {gymReport && (
          <section className="output-section gym-output">
            <div className="compliance-header">
              <div
                className="compliance-status-badge"
                style={{ backgroundColor: getRiskColor(gymReport.overall_risk) }}
              >
                {getRiskLabel(gymReport.overall_risk)}
              </div>
              <div className="risk-exposure">
                <span className="label">CANCEL DIFFICULTY:</span>
                <span className="value">{gymReport.cancellation_difficulty.toUpperCase()}</span>
              </div>
            </div>

            <p className="summary-text">{gymReport.summary}</p>

            <div className="tabs">
              <button
                className={`tab ${gymTab === 'report' ? 'active' : ''}`}
                onClick={() => setGymTab('report')}
              >
                * ANALYSIS
              </button>
              <button
                className={`tab ${gymTab === 'letter' ? 'active' : ''}`}
                onClick={() => setGymTab('letter')}
              >
                * CANCELLATION GUIDE
              </button>
            </div>

            {gymTab === 'report' && (
              <div className="compliance-report">
                {gymReport.red_flags.filter(rf => rf.severity === 'critical').length > 0 && (
                  <div className="data-card danger full-width">
                    <h3>XX CRITICAL RED FLAGS</h3>
                    <div className="compliance-items">
                      {gymReport.red_flags.filter(rf => rf.severity === 'critical').map((flag, i) => (
                        <div key={i} className="compliance-item fail">
                          <div className="item-header">
                            <span className="status-icon">✗</span>
                            <span className="item-name">{flag.name}</span>
                          </div>
                          {flag.clause_text && (
                            <div className="clause-text">
                              <span className="label">CLAUSE:</span>
                              <span className="value">"{flag.clause_text}"</span>
                            </div>
                          )}
                          <p className="item-explanation">{flag.explanation}</p>
                          <div className="protection-box">
                            <span className="label">PROTECTION:</span>
                            <span className="value">{flag.protection}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {gymReport.red_flags.filter(rf => rf.severity === 'warning').length > 0 && (
                  <div className="data-card warning full-width">
                    <h3>!! WATCH OUT FOR</h3>
                    <div className="compliance-items">
                      {gymReport.red_flags.filter(rf => rf.severity === 'warning').map((flag, i) => (
                        <div key={i} className="compliance-item warning">
                          <div className="item-header">
                            <span className="status-icon">!</span>
                            <span className="item-name">{flag.name}</span>
                          </div>
                          {flag.clause_text && (
                            <div className="clause-text">
                              <span className="label">CLAUSE:</span>
                              <span className="value">"{flag.clause_text}"</span>
                            </div>
                          )}
                          <p className="item-explanation">{flag.explanation}</p>
                          <div className="protection-box">
                            <span className="label">PROTECTION:</span>
                            <span className="value">{flag.protection}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {gymReport.state_protections.length > 0 && (
                  <div className="data-card success full-width">
                    <h3>** YOUR STATE PROTECTIONS</h3>
                    <div className="missing-list">
                      {gymReport.state_protections.map((item, i) => (
                        <div key={i} className="missing-item">
                          <span className="status-icon">✓</span>
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
                      <span className="label">GYM:</span>
                      <span className="value">{gymReport.gym_name || '---'}</span>
                    </div>
                    <div className="data-row">
                      <span className="label">TYPE:</span>
                      <span className="value">{gymReport.contract_type?.toUpperCase() || '---'}</span>
                    </div>
                    <div className="data-row">
                      <span className="label">MONTHLY:</span>
                      <span className="value mono">{gymReport.monthly_fee || '---'}</span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {gymTab === 'letter' && (
              <div className="letter-view">
                <div className="letter-content">
                  <pre>{gymReport.cancellation_guide}</pre>
                </div>
                <button
                  className="pixel-btn secondary"
                  onClick={() => navigator.clipboard.writeText(gymReport.cancellation_guide)}
                >
                  [COPY] COPY GUIDE
                </button>
              </div>
            )}
          </section>
        )}

        {/* Employment Contract Results */}
        {employmentReport && (
          <section className="output-section employment-output">
            <div className="compliance-header">
              <div
                className="compliance-status-badge"
                style={{ backgroundColor: getRiskColor(employmentReport.overall_risk) }}
              >
                {getRiskLabel(employmentReport.overall_risk)}
              </div>
              <div className="risk-exposure">
                <span className="label">RISK SCORE:</span>
                <span className="value">{employmentReport.risk_score}/100</span>
              </div>
            </div>

            <p className="summary-text">{employmentReport.summary}</p>

            <div className="tabs">
              <button
                className={`tab ${employmentTab === 'report' ? 'active' : ''}`}
                onClick={() => setEmploymentTab('report')}
              >
                * ANALYSIS
              </button>
              <button
                className={`tab ${employmentTab === 'letter' ? 'active' : ''}`}
                onClick={() => setEmploymentTab('letter')}
              >
                * NEGOTIATION POINTS
              </button>
            </div>

            {employmentTab === 'report' && (
              <div className="compliance-report">
                {employmentReport.red_flags.filter(rf => rf.severity === 'critical').length > 0 && (
                  <div className="data-card danger full-width">
                    <h3>XX CRITICAL RED FLAGS</h3>
                    <div className="compliance-items">
                      {employmentReport.red_flags.filter(rf => rf.severity === 'critical').map((flag, i) => (
                        <div key={i} className="compliance-item fail">
                          <div className="item-header">
                            <span className="status-icon">✗</span>
                            <span className="item-name">{flag.name}</span>
                          </div>
                          {flag.clause_text && (
                            <div className="clause-text">
                              <span className="label">CLAUSE:</span>
                              <span className="value">"{flag.clause_text}"</span>
                            </div>
                          )}
                          <p className="item-explanation">{flag.explanation}</p>
                          <div className="protection-box">
                            <span className="label">PROTECTION:</span>
                            <span className="value">{flag.protection}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {employmentReport.red_flags.filter(rf => rf.severity === 'warning').length > 0 && (
                  <div className="data-card warning full-width">
                    <h3>!! WATCH OUT FOR</h3>
                    <div className="compliance-items">
                      {employmentReport.red_flags.filter(rf => rf.severity === 'warning').map((flag, i) => (
                        <div key={i} className="compliance-item warning">
                          <div className="item-header">
                            <span className="status-icon">!</span>
                            <span className="item-name">{flag.name}</span>
                          </div>
                          {flag.clause_text && (
                            <div className="clause-text">
                              <span className="label">CLAUSE:</span>
                              <span className="value">"{flag.clause_text}"</span>
                            </div>
                          )}
                          <p className="item-explanation">{flag.explanation}</p>
                          <div className="protection-box">
                            <span className="label">PROTECTION:</span>
                            <span className="value">{flag.protection}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {employmentReport.state_notes.length > 0 && (
                  <div className="data-card info full-width">
                    <h3>?? STATE-SPECIFIC NOTES</h3>
                    <div className="missing-list">
                      {employmentReport.state_notes.map((item, i) => (
                        <div key={i} className="missing-item">
                          <span className="status-icon">*</span>
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
                      <span className="label">TYPE:</span>
                      <span className="value">{employmentReport.document_type?.replace(/_/g, ' ').toUpperCase() || '---'}</span>
                    </div>
                    <div className="data-row">
                      <span className="label">NON-COMPETE:</span>
                      <span className={`value ${employmentReport.has_non_compete ? 'fail' : 'pass'}`}>
                        {employmentReport.has_non_compete ? 'YES' : 'NO'}
                      </span>
                    </div>
                    {employmentReport.has_non_compete && (
                      <div className="data-row">
                        <span className="label">ENFORCEABLE:</span>
                        <span className="value">{employmentReport.non_compete_enforceable?.toUpperCase() || '---'}</span>
                      </div>
                    )}
                    <div className="data-row">
                      <span className="label">ARBITRATION:</span>
                      <span className={`value ${employmentReport.has_arbitration ? 'fail' : 'pass'}`}>
                        {employmentReport.has_arbitration ? 'YES' : 'NO'}
                      </span>
                    </div>
                    <div className="data-row">
                      <span className="label">IP ASSIGNMENT:</span>
                      <span className={`value ${employmentReport.has_ip_assignment ? 'fail' : ''}`}>
                        {employmentReport.has_ip_assignment ? 'YES' : 'NO'}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {employmentTab === 'letter' && (
              <div className="letter-view">
                <div className="letter-content">
                  <pre>{employmentReport.negotiation_points}</pre>
                </div>
                <button
                  className="pixel-btn secondary"
                  onClick={() => navigator.clipboard.writeText(employmentReport.negotiation_points)}
                >
                  [COPY] COPY POINTS
                </button>
              </div>
            )}
          </section>
        )}

        {/* Freelancer Contract Results */}
        {freelancerReport && (
          <section className="output-section freelancer-output">
            <div className="compliance-header">
              <div
                className="compliance-status-badge"
                style={{ backgroundColor: getRiskColor(freelancerReport.overall_risk) }}
              >
                {getRiskLabel(freelancerReport.overall_risk)}
              </div>
              <div className="risk-exposure">
                <span className="label">RISK SCORE:</span>
                <span className="value">{freelancerReport.risk_score}/100</span>
              </div>
            </div>

            <p className="summary-text">{freelancerReport.summary}</p>

            <div className="tabs">
              <button
                className={`tab ${freelancerTab === 'report' ? 'active' : ''}`}
                onClick={() => setFreelancerTab('report')}
              >
                * ANALYSIS
              </button>
              <button
                className={`tab ${freelancerTab === 'letter' ? 'active' : ''}`}
                onClick={() => setFreelancerTab('letter')}
              >
                * SUGGESTED CHANGES
              </button>
            </div>

            {freelancerTab === 'report' && (
              <div className="compliance-report">
                {freelancerReport.red_flags.filter(rf => rf.severity === 'critical').length > 0 && (
                  <div className="data-card danger full-width">
                    <h3>XX CRITICAL RED FLAGS</h3>
                    <div className="compliance-items">
                      {freelancerReport.red_flags.filter(rf => rf.severity === 'critical').map((flag, i) => (
                        <div key={i} className="compliance-item fail">
                          <div className="item-header">
                            <span className="status-icon">✗</span>
                            <span className="item-name">{flag.name}</span>
                          </div>
                          {flag.clause_text && (
                            <div className="clause-text">
                              <span className="label">CLAUSE:</span>
                              <span className="value">"{flag.clause_text}"</span>
                            </div>
                          )}
                          <p className="item-explanation">{flag.explanation}</p>
                          <div className="protection-box">
                            <span className="label">PROTECTION:</span>
                            <span className="value">{flag.protection}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {freelancerReport.red_flags.filter(rf => rf.severity === 'warning').length > 0 && (
                  <div className="data-card warning full-width">
                    <h3>!! WATCH OUT FOR</h3>
                    <div className="compliance-items">
                      {freelancerReport.red_flags.filter(rf => rf.severity === 'warning').map((flag, i) => (
                        <div key={i} className="compliance-item warning">
                          <div className="item-header">
                            <span className="status-icon">!</span>
                            <span className="item-name">{flag.name}</span>
                          </div>
                          {flag.clause_text && (
                            <div className="clause-text">
                              <span className="label">CLAUSE:</span>
                              <span className="value">"{flag.clause_text}"</span>
                            </div>
                          )}
                          <p className="item-explanation">{flag.explanation}</p>
                          <div className="protection-box">
                            <span className="label">PROTECTION:</span>
                            <span className="value">{flag.protection}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {freelancerReport.missing_protections.length > 0 && (
                  <div className="data-card info full-width">
                    <h3>?? MISSING PROTECTIONS</h3>
                    <div className="missing-list">
                      {freelancerReport.missing_protections.map((item, i) => (
                        <div key={i} className="missing-item">
                          <span className="status-icon">-</span>
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
                      <span className="label">TYPE:</span>
                      <span className="value">{freelancerReport.contract_type?.toUpperCase() || '---'}</span>
                    </div>
                    <div className="data-row">
                      <span className="label">PAYMENT:</span>
                      <span className="value">{freelancerReport.payment_terms || '---'}</span>
                    </div>
                    <div className="data-row">
                      <span className="label">IP OWNERSHIP:</span>
                      <span className="value">{freelancerReport.ip_ownership?.replace(/_/g, ' ').toUpperCase() || '---'}</span>
                    </div>
                    <div className="data-row">
                      <span className="label">KILL FEE:</span>
                      <span className={`value ${freelancerReport.has_kill_fee ? 'pass' : 'fail'}`}>
                        {freelancerReport.has_kill_fee ? 'YES' : 'NO'}
                      </span>
                    </div>
                    <div className="data-row">
                      <span className="label">REVISIONS:</span>
                      <span className="value">{freelancerReport.revision_limit || 'UNLIMITED'}</span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {freelancerTab === 'letter' && (
              <div className="letter-view">
                <div className="letter-content">
                  <pre>{freelancerReport.suggested_changes}</pre>
                </div>
                <button
                  className="pixel-btn secondary"
                  onClick={() => navigator.clipboard.writeText(freelancerReport.suggested_changes)}
                >
                  [COPY] COPY CHANGES
                </button>
              </div>
            )}
          </section>
        )}

        {/* Influencer Contract Results */}
        {influencerReport && (
          <section className="output-section influencer-output">
            <div className="compliance-header">
              <div
                className="compliance-status-badge"
                style={{ backgroundColor: getRiskColor(influencerReport.overall_risk) }}
              >
                {getRiskLabel(influencerReport.overall_risk)}
              </div>
              <div className="risk-exposure">
                <span className="label">FTC COMPLIANCE:</span>
                <span className={`value ${influencerReport.ftc_compliance === 'addressed' ? 'pass' : influencerReport.ftc_compliance === 'missing' ? 'fail' : ''}`}>
                  {influencerReport.ftc_compliance.toUpperCase()}
                </span>
              </div>
            </div>

            <p className="summary-text">{influencerReport.summary}</p>

            <div className="tabs">
              <button
                className={`tab ${influencerTab === 'report' ? 'active' : ''}`}
                onClick={() => setInfluencerTab('report')}
              >
                * ANALYSIS
              </button>
              <button
                className={`tab ${influencerTab === 'letter' ? 'active' : ''}`}
                onClick={() => setInfluencerTab('letter')}
              >
                * NEGOTIATION SCRIPT
              </button>
            </div>

            {influencerTab === 'report' && (
              <div className="compliance-report">
                {influencerReport.red_flags.filter(rf => rf.severity === 'critical').length > 0 && (
                  <div className="data-card danger full-width">
                    <h3>XX CRITICAL RED FLAGS</h3>
                    <div className="compliance-items">
                      {influencerReport.red_flags.filter(rf => rf.severity === 'critical').map((flag, i) => (
                        <div key={i} className="compliance-item fail">
                          <div className="item-header">
                            <span className="status-icon">✗</span>
                            <span className="item-name">{flag.name}</span>
                          </div>
                          {flag.clause_text && (
                            <div className="clause-text">
                              <span className="label">CLAUSE:</span>
                              <span className="value">"{flag.clause_text}"</span>
                            </div>
                          )}
                          <p className="item-explanation">{flag.explanation}</p>
                          <div className="protection-box">
                            <span className="label">PROTECTION:</span>
                            <span className="value">{flag.protection}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {influencerReport.red_flags.filter(rf => rf.severity === 'warning').length > 0 && (
                  <div className="data-card warning full-width">
                    <h3>!! WATCH OUT FOR</h3>
                    <div className="compliance-items">
                      {influencerReport.red_flags.filter(rf => rf.severity === 'warning').map((flag, i) => (
                        <div key={i} className="compliance-item warning">
                          <div className="item-header">
                            <span className="status-icon">!</span>
                            <span className="item-name">{flag.name}</span>
                          </div>
                          {flag.clause_text && (
                            <div className="clause-text">
                              <span className="label">CLAUSE:</span>
                              <span className="value">"{flag.clause_text}"</span>
                            </div>
                          )}
                          <p className="item-explanation">{flag.explanation}</p>
                          <div className="protection-box">
                            <span className="label">PROTECTION:</span>
                            <span className="value">{flag.protection}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div className="data-card full-width">
                  <h3>* CONTRACT INFO</h3>
                  <div className="coi-data-grid">
                    <div className="data-row">
                      <span className="label">BRAND:</span>
                      <span className="value">{influencerReport.brand_name || '---'}</span>
                    </div>
                    <div className="data-row">
                      <span className="label">CAMPAIGN:</span>
                      <span className="value">{influencerReport.campaign_type?.replace(/_/g, ' ').toUpperCase() || '---'}</span>
                    </div>
                    <div className="data-row">
                      <span className="label">USAGE RIGHTS:</span>
                      <span className="value">{influencerReport.usage_rights_duration || '---'}</span>
                    </div>
                    <div className="data-row">
                      <span className="label">EXCLUSIVITY:</span>
                      <span className="value">{influencerReport.exclusivity_scope || 'NONE'}</span>
                    </div>
                    <div className="data-row">
                      <span className="label">PERPETUAL:</span>
                      <span className={`value ${influencerReport.has_perpetual_rights ? 'fail' : 'pass'}`}>
                        {influencerReport.has_perpetual_rights ? 'YES' : 'NO'}
                      </span>
                    </div>
                    <div className="data-row">
                      <span className="label">AI TRAINING:</span>
                      <span className={`value ${influencerReport.has_ai_training_rights ? 'fail' : 'pass'}`}>
                        {influencerReport.has_ai_training_rights ? 'YES' : 'NO'}
                      </span>
                    </div>
                    <div className="data-row">
                      <span className="label">PAYMENT:</span>
                      <span className="value">{influencerReport.payment_terms || '---'}</span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {influencerTab === 'letter' && (
              <div className="letter-view">
                <div className="letter-content">
                  <pre>{influencerReport.negotiation_script}</pre>
                </div>
                <button
                  className="pixel-btn secondary"
                  onClick={() => navigator.clipboard.writeText(influencerReport.negotiation_script)}
                >
                  [COPY] COPY SCRIPT
                </button>
              </div>
            )}
          </section>
        )}

        {/* Timeshare Contract Results */}
        {timeshareReport && (
          <section className="output-section timeshare-output">
            <div className="compliance-header">
              <div
                className="compliance-status-badge"
                style={{ backgroundColor: getRiskColor(timeshareReport.overall_risk) }}
              >
                {getRiskLabel(timeshareReport.overall_risk)}
              </div>
              <div className="risk-exposure">
                <span className="label">10-YEAR COST:</span>
                <span className="value">{timeshareReport.estimated_10yr_cost || 'UNKNOWN'}</span>
              </div>
            </div>

            <p className="summary-text">{timeshareReport.summary}</p>

            <div className="tabs">
              <button
                className={`tab ${timeshareTab === 'report' ? 'active' : ''}`}
                onClick={() => setTimeshareTab('report')}
              >
                * ANALYSIS
              </button>
              <button
                className={`tab ${timeshareTab === 'letter' ? 'active' : ''}`}
                onClick={() => setTimeshareTab('letter')}
              >
                * RESCISSION LETTER
              </button>
            </div>

            {timeshareTab === 'report' && (
              <div className="compliance-report">
                {timeshareReport.red_flags.filter(rf => rf.severity === 'critical').length > 0 && (
                  <div className="data-card danger full-width">
                    <h3>XX CRITICAL RED FLAGS</h3>
                    <div className="compliance-items">
                      {timeshareReport.red_flags.filter(rf => rf.severity === 'critical').map((flag, i) => (
                        <div key={i} className="compliance-item fail">
                          <div className="item-header">
                            <span className="status-icon">✗</span>
                            <span className="item-name">{flag.name}</span>
                          </div>
                          {flag.clause_text && (
                            <div className="clause-text">
                              <span className="label">CLAUSE:</span>
                              <span className="value">"{flag.clause_text}"</span>
                            </div>
                          )}
                          <p className="item-explanation">{flag.explanation}</p>
                          <div className="protection-box">
                            <span className="label">PROTECTION:</span>
                            <span className="value">{flag.protection}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {timeshareReport.red_flags.filter(rf => rf.severity === 'warning').length > 0 && (
                  <div className="data-card warning full-width">
                    <h3>!! WATCH OUT FOR</h3>
                    <div className="compliance-items">
                      {timeshareReport.red_flags.filter(rf => rf.severity === 'warning').map((flag, i) => (
                        <div key={i} className="compliance-item warning">
                          <div className="item-header">
                            <span className="status-icon">!</span>
                            <span className="item-name">{flag.name}</span>
                          </div>
                          {flag.clause_text && (
                            <div className="clause-text">
                              <span className="label">CLAUSE:</span>
                              <span className="value">"{flag.clause_text}"</span>
                            </div>
                          )}
                          <p className="item-explanation">{flag.explanation}</p>
                          <div className="protection-box">
                            <span className="label">PROTECTION:</span>
                            <span className="value">{flag.protection}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {timeshareReport.exit_options.length > 0 && (
                  <div className="data-card info full-width">
                    <h3>?? EXIT OPTIONS</h3>
                    <div className="missing-list">
                      {timeshareReport.exit_options.map((item, i) => (
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
                      <span className="value">{timeshareReport.resort_name || '---'}</span>
                    </div>
                    <div className="data-row">
                      <span className="label">OWNERSHIP:</span>
                      <span className="value">{timeshareReport.ownership_type?.replace(/_/g, ' ').toUpperCase() || '---'}</span>
                    </div>
                    <div className="data-row">
                      <span className="label">PERPETUITY:</span>
                      <span className={`value ${timeshareReport.has_perpetuity_clause ? 'fail' : 'pass'}`}>
                        {timeshareReport.has_perpetuity_clause ? 'YES - FOREVER' : 'NO'}
                      </span>
                    </div>
                    <div className="data-row">
                      <span className="label">RESCISSION:</span>
                      <span className={`value ${timeshareReport.rescission_deadline ? '' : 'fail'}`}>
                        {timeshareReport.rescission_deadline || 'CHECK STATE LAW'}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {timeshareTab === 'letter' && (
              <div className="letter-view">
                <div className="letter-content">
                  <pre>{timeshareReport.rescission_letter}</pre>
                </div>
                <button
                  className="pixel-btn secondary"
                  onClick={() => navigator.clipboard.writeText(timeshareReport.rescission_letter)}
                >
                  [COPY] COPY LETTER
                </button>
              </div>
            )}
          </section>
        )}

        {/* Insurance Policy Results */}
        {insurancePolicyReport && (
          <section className="output-section insurance-policy-output">
            <div className="compliance-header">
              <div
                className="compliance-status-badge"
                style={{ backgroundColor: getRiskColor(insurancePolicyReport.overall_risk) }}
              >
                {getRiskLabel(insurancePolicyReport.overall_risk)}
              </div>
              <div className="risk-exposure">
                <span className="label">VALUATION:</span>
                <span className={`value ${insurancePolicyReport.valuation_method === 'actual_cash_value' ? 'fail' : ''}`}>
                  {insurancePolicyReport.valuation_method?.replace(/_/g, ' ').toUpperCase() || '---'}
                </span>
              </div>
            </div>

            <p className="summary-text">{insurancePolicyReport.summary}</p>

            <div className="tabs">
              <button
                className={`tab ${insurancePolicyTab === 'report' ? 'active' : ''}`}
                onClick={() => setInsurancePolicyTab('report')}
              >
                * ANALYSIS
              </button>
              <button
                className={`tab ${insurancePolicyTab === 'letter' ? 'active' : ''}`}
                onClick={() => setInsurancePolicyTab('letter')}
              >
                * QUESTIONS FOR AGENT
              </button>
            </div>

            {insurancePolicyTab === 'report' && (
              <div className="compliance-report">
                {insurancePolicyReport.red_flags.filter(rf => rf.severity === 'critical').length > 0 && (
                  <div className="data-card danger full-width">
                    <h3>XX CRITICAL RED FLAGS</h3>
                    <div className="compliance-items">
                      {insurancePolicyReport.red_flags.filter(rf => rf.severity === 'critical').map((flag, i) => (
                        <div key={i} className="compliance-item fail">
                          <div className="item-header">
                            <span className="status-icon">✗</span>
                            <span className="item-name">{flag.name}</span>
                          </div>
                          {flag.clause_text && (
                            <div className="clause-text">
                              <span className="label">CLAUSE:</span>
                              <span className="value">"{flag.clause_text}"</span>
                            </div>
                          )}
                          <p className="item-explanation">{flag.explanation}</p>
                          <div className="protection-box">
                            <span className="label">ASK AGENT:</span>
                            <span className="value">{flag.what_to_ask}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {insurancePolicyReport.red_flags.filter(rf => rf.severity === 'warning').length > 0 && (
                  <div className="data-card warning full-width">
                    <h3>!! WATCH OUT FOR</h3>
                    <div className="compliance-items">
                      {insurancePolicyReport.red_flags.filter(rf => rf.severity === 'warning').map((flag, i) => (
                        <div key={i} className="compliance-item warning">
                          <div className="item-header">
                            <span className="status-icon">!</span>
                            <span className="item-name">{flag.name}</span>
                          </div>
                          {flag.clause_text && (
                            <div className="clause-text">
                              <span className="label">CLAUSE:</span>
                              <span className="value">"{flag.clause_text}"</span>
                            </div>
                          )}
                          <p className="item-explanation">{flag.explanation}</p>
                          <div className="protection-box">
                            <span className="label">ASK AGENT:</span>
                            <span className="value">{flag.what_to_ask}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {insurancePolicyReport.coverage_gaps.length > 0 && (
                  <div className="data-card info full-width">
                    <h3>?? COVERAGE GAPS</h3>
                    <div className="missing-list">
                      {insurancePolicyReport.coverage_gaps.map((item, i) => (
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
                      <span className="value">{insurancePolicyReport.policy_type?.toUpperCase() || '---'}</span>
                    </div>
                    <div className="data-row">
                      <span className="label">CARRIER:</span>
                      <span className="value">{insurancePolicyReport.carrier || '---'}</span>
                    </div>
                    <div className="data-row">
                      <span className="label">COVERAGE:</span>
                      <span className="value">{insurancePolicyReport.coverage_type?.replace(/_/g, ' ').toUpperCase() || '---'}</span>
                    </div>
                    <div className="data-row">
                      <span className="label">DEDUCTIBLE:</span>
                      <span className={`value ${insurancePolicyReport.deductible_type === 'percentage' ? 'fail' : ''}`}>
                        {insurancePolicyReport.deductible_type?.toUpperCase() || '---'}
                      </span>
                    </div>
                    <div className="data-row">
                      <span className="label">ARBITRATION:</span>
                      <span className={`value ${insurancePolicyReport.has_arbitration ? 'fail' : 'pass'}`}>
                        {insurancePolicyReport.has_arbitration ? 'YES' : 'NO'}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {insurancePolicyTab === 'letter' && (
              <div className="letter-view">
                <div className="letter-content">
                  <pre>{insurancePolicyReport.questions_for_agent}</pre>
                </div>
                <button
                  className="pixel-btn secondary"
                  onClick={() => navigator.clipboard.writeText(insurancePolicyReport.questions_for_agent)}
                >
                  [COPY] COPY QUESTIONS
                </button>
              </div>
            )}
          </section>
        )}
      </main>

      {/* Disclaimer Modal */}
      {showDisclaimerModal && (
        <div className="modal-overlay">
          <div className="modal disclaimer-modal">
            <div className="modal-header">
              <span className="modal-icon">[!]</span>
              <h2>HOLD UP</h2>
            </div>
            <div className="modal-content">
              <p>Hey! I'm trying my best here but <strong>I'm not a lawyer</strong> and neither is Claude!</p>
              <p>This tool is for <strong>educational purposes only</strong>. It might miss things. It might be wrong. If you need a lawyer, get a lawyer dawg.</p>
              <p className="modal-cta">Type <strong>"not legal advice"</strong> to confirm you understand:</p>
              <input
                type="text"
                className="pixel-input"
                placeholder="not legal advice"
                value={disclaimerInput}
                onChange={(e) => setDisclaimerInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleDisclaimerSubmit()}
                autoFocus
              />
              <div className="modal-buttons">
                <button
                  className="pixel-btn primary"
                  onClick={handleDisclaimerSubmit}
                  disabled={disclaimerInput.toLowerCase().trim() !== 'not legal advice'}
                >
                  [GOT IT]
                </button>
                <button className="pixel-btn secondary" onClick={handleDisclaimerCancel}>
                  [BACK]
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

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

      {/* Loading Overlay with Affiliate Offers */}
      {loading && (
        <div className="loading-overlay">
          <div className="loading-content">
            <div className="loading-spinner">
              <div className="spinner-pixel"></div>
            </div>
            <h2 className="loading-title">ANALYZING YOUR DOCUMENT...</h2>
            <p className="loading-subtitle">This usually takes 10-15 seconds</p>

            {/* Affiliate Offer */}
            {currentOffer && (
              <div className="affiliate-card">
                <div className="affiliate-badge">WHILE YOU WAIT</div>
                <h3 className="affiliate-name">{currentOffer.name}</h3>
                <p className="affiliate-tagline">{currentOffer.tagline}</p>
                <p className="affiliate-description">{currentOffer.description}</p>
                <a
                  href={currentOffer.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="affiliate-cta"
                  onClick={() => {
                    // Track click (would be analytics in production)
                    console.log('Affiliate click:', currentOffer.id)
                  }}
                >
                  {currentOffer.cta} &rarr;
                </a>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Auth Modal */}
      {showAuthModal && (
        <div className="modal-overlay" onClick={() => setShowAuthModal(false)}>
          <div className="modal auth-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <span className="modal-icon">[*]</span>
              <h2>{authMode === 'login' ? 'LOG IN' : 'SIGN UP'}</h2>
            </div>
            <div className="modal-content">
              <p className="auth-benefit">
                Sign in to save your analysis history and access it anytime.
              </p>

              {authError && (
                <div className="auth-error">{authError}</div>
              )}

              <input
                type="email"
                className="pixel-input"
                placeholder="Email"
                value={authEmail}
                onChange={(e) => setAuthEmail(e.target.value)}
                disabled={authLoading}
              />
              <input
                type="password"
                className="pixel-input"
                placeholder="Password"
                value={authPassword}
                onChange={(e) => setAuthPassword(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && (authMode === 'login' ? handleLogin() : handleSignup())}
                disabled={authLoading}
              />

              <div className="modal-buttons">
                <button
                  className="pixel-btn primary"
                  onClick={authMode === 'login' ? handleLogin : handleSignup}
                  disabled={authLoading || !authEmail || !authPassword}
                >
                  {authLoading ? '[...]' : authMode === 'login' ? '[LOG IN]' : '[SIGN UP]'}
                </button>
                <button className="pixel-btn secondary" onClick={() => setShowAuthModal(false)}>
                  [CANCEL]
                </button>
              </div>

              <p className="auth-switch">
                {authMode === 'login' ? (
                  <>Don't have an account? <button className="link-btn" onClick={() => setAuthMode('signup')}>Sign up</button></>
                ) : (
                  <>Already have an account? <button className="link-btn" onClick={() => setAuthMode('login')}>Log in</button></>
                )}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* History Modal */}
      {showHistoryModal && (
        <div className="modal-overlay" onClick={() => setShowHistoryModal(false)}>
          <div className="modal history-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <span className="modal-icon">[H]</span>
              <h2>YOUR HISTORY</h2>
            </div>
            <div className="modal-content">
              {historyLoading ? (
                <p className="loading-text">Loading...</p>
              ) : userHistory.length === 0 ? (
                <p>No documents analyzed yet. Upload one to get started!</p>
              ) : (
                <div className="history-list">
                  {userHistory.map((item) => (
                    <div key={item.id} className="history-item">
                      <div className="history-item-header">
                        <span className="history-type">{item.document_type.toUpperCase()}</span>
                        <span className={`history-risk risk-${item.overall_risk}`}>
                          {item.overall_risk.toUpperCase()}
                        </span>
                      </div>
                      <div className="history-item-meta">
                        <span className="history-score">Score: {item.risk_score}/100</span>
                        <span className="history-date">
                          {new Date(item.created_at).toLocaleDateString()}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
              <div className="modal-buttons">
                <button className="pixel-btn secondary" onClick={() => setShowHistoryModal(false)}>
                  [CLOSE]
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      <footer className="footer">
        <a
          href={STRIPE_DONATION_LINK}
          target="_blank"
          rel="noopener noreferrer"
          className="donate-link-footer"
        >
          {donationText.isHtml ? (
            <span dangerouslySetInnerHTML={{ __html: donationText.text }} />
          ) : (
            donationText.text
          )}
        </a>
        <a
          href="https://github.com/discordwell/insurance-llm"
          target="_blank"
          rel="noopener noreferrer"
          className="github-link-small"
        >
          github
        </a>
      </footer>
    </div>
  )
}

export default App
