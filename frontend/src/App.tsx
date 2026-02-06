import { useState, useEffect } from 'react'
import './App.css'
import { getOffersForDocType } from './config/affiliates'
import type { AffiliateOffer } from './config/affiliates'
import { STRIPE_DONATION_LINK } from './config/stripe'
import { API_BASE } from './services/api'
import { donationTexts } from './constants/donation'
import type {
  ComplianceReport,
  LeaseAnalysisReport,
  GymContractReport,
  EmploymentContractReport,
  FreelancerContractReport,
  InfluencerContractReport,
  TimeshareContractReport,
  InsurancePolicyReport,
} from './types'

// Hooks
import { useAuth } from './hooks/useAuth'
import { useDocumentUpload } from './hooks/useDocumentUpload'
import { useAnalyzer } from './hooks/useAnalyzer'
import { useDisclaimer } from './hooks/useDisclaimer'

// Components
import Header from './components/Header'
import InputSection from './components/InputSection'
import Footer from './components/Footer'
import LoadingOverlay from './components/LoadingOverlay'
import DisclaimerModal from './components/modals/DisclaimerModal'
import UnsupportedModal from './components/modals/UnsupportedModal'
import AuthModal from './components/modals/AuthModal'
import HistoryModal from './components/modals/HistoryModal'

// Reports
import COIReport from './components/reports/COIReport'
import LeaseReport from './components/reports/LeaseReport'
import GymReport from './components/reports/GymReport'
import EmploymentReport from './components/reports/EmploymentReport'
import FreelancerReport from './components/reports/FreelancerReport'
import InfluencerReport from './components/reports/InfluencerReport'
import TimeshareReport from './components/reports/TimeshareReport'
import InsurancePolicyReport_ from './components/reports/InsurancePolicyReport'

function App() {
  const [scanLines] = useState(true)

  // Donation text - randomized on mount
  const [donationText] = useState(() => donationTexts[Math.floor(Math.random() * donationTexts.length)])

  // Affiliate offer state
  const [currentOffer, setCurrentOffer] = useState<AffiliateOffer | null>(null)
  const [, setOfferIndex] = useState(0)

  // Auth hook
  const auth = useAuth()

  // Analyzers (each manages its own report + tab + loading state)
  const coi = useAnalyzer<ComplianceReport>(auth.authToken)
  const lease = useAnalyzer<LeaseAnalysisReport>(auth.authToken)
  const gym = useAnalyzer<GymContractReport>(auth.authToken)
  const employment = useAnalyzer<EmploymentContractReport>(auth.authToken)
  const freelancer = useAnalyzer<FreelancerContractReport>(auth.authToken)
  const influencer = useAnalyzer<InfluencerContractReport>(auth.authToken)
  const timeshare = useAnalyzer<TimeshareContractReport>(auth.authToken)
  const insurancePolicy = useAnalyzer<InsurancePolicyReport>(auth.authToken)

  const resetAllReports = () => {
    coi.reset()
    lease.reset()
    gym.reset()
    employment.reset()
    freelancer.reset()
    influencer.reset()
    timeshare.reset()
    insurancePolicy.reset()
  }

  // Document upload hook
  const upload = useDocumentUpload({ onReportsReset: resetAllReports })

  // Combined loading state
  const anyLoading = coi.loading || lease.loading || gym.loading || employment.loading ||
    freelancer.loading || influencer.loading || timeshare.loading || insurancePolicy.loading

  // Run the right analyzer based on doc type
  const runAnalysis = async (docTypeStr: string | undefined) => {
    switch (docTypeStr) {
      case 'coi':
        await coi.analyze({
          endpoint: '/api/check-coi-compliance',
          buildBody: () => ({ coi_text: upload.docText, project_type: upload.projectType, state: upload.selectedState || null }),
          errorMessage: 'Compliance check failed.',
        })
        break
      case 'lease':
        await lease.analyze({
          endpoint: '/api/analyze-lease',
          buildBody: () => ({ lease_text: upload.docText, state: upload.selectedState || null, lease_type: 'commercial' }),
          errorMessage: 'Lease analysis failed.',
        })
        break
      case 'gym':
        await gym.analyze({
          endpoint: '/api/analyze-gym',
          buildBody: () => ({ contract_text: upload.docText, state: upload.selectedState || null }),
          errorMessage: 'Gym contract analysis failed.',
        })
        break
      case 'employment':
        await employment.analyze({
          endpoint: '/api/analyze-employment',
          buildBody: () => ({ contract_text: upload.docText, state: upload.selectedState || null }),
          errorMessage: 'Employment contract analysis failed.',
        })
        break
      case 'freelancer':
        await freelancer.analyze({
          endpoint: '/api/analyze-freelancer',
          buildBody: () => ({ contract_text: upload.docText }),
          errorMessage: 'Freelancer contract analysis failed.',
        })
        break
      case 'influencer':
        await influencer.analyze({
          endpoint: '/api/analyze-influencer',
          buildBody: () => ({ contract_text: upload.docText }),
          errorMessage: 'Influencer contract analysis failed.',
        })
        break
      case 'timeshare':
        await timeshare.analyze({
          endpoint: '/api/analyze-timeshare',
          buildBody: () => ({ contract_text: upload.docText, state: upload.selectedState || null }),
          errorMessage: 'Timeshare contract analysis failed.',
        })
        break
      case 'insurance_policy':
        await insurancePolicy.analyze({
          endpoint: '/api/analyze-insurance-policy',
          buildBody: () => ({ policy_text: upload.docText, state: upload.selectedState || null }),
          errorMessage: 'Insurance policy analysis failed.',
        })
        break
    }
  }

  // Disclaimer hook
  const disclaimer = useDisclaimer({ runAnalysis })

  // Handle analyze button
  const handleAnalyze = async () => {
    if (!upload.docText.trim()) return

    // If no classification yet, classify first
    let currentDocType = upload.docType
    if (!currentDocType) {
      const classification = await upload.classifyDocument(upload.docText)
      upload.handleClassification(classification)
      if (!classification?.supported) return
      upload.setDocType(classification)
      currentDocType = classification
    }

    // If disclaimer not yet accepted, show the modal
    if (!disclaimer.disclaimerAccepted) {
      const docTypeStr = currentDocType?.document_type
      if (docTypeStr && ['coi', 'lease', 'gym', 'employment', 'freelancer', 'influencer', 'timeshare', 'insurance_policy'].includes(docTypeStr)) {
        disclaimer.setPendingAnalysis(docTypeStr as 'coi' | 'lease' | 'gym' | 'employment' | 'freelancer' | 'influencer' | 'timeshare' | 'insurance_policy')
      }
      disclaimer.setShowDisclaimerModal(true)
      disclaimer.setDisclaimerInput('')
      return
    }

    // Route to appropriate analyzer
    await runAnalysis(currentDocType?.document_type)
  }

  // Waitlist submit
  const handleWaitlistSubmit = async () => {
    try {
      await fetch(`${API_BASE}/api/waitlist`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: upload.waitlistEmail,
          document_type: upload.unsupportedType,
          document_text: upload.docText
        })
      })
    } catch (err) {
      console.error('Waitlist signup failed:', err)
    }
    upload.setEmailSubmitted(true)
  }

  // Reset all state
  const resetAll = () => {
    upload.setUploadedFileName(null)
    upload.setDocText('')
    upload.setDocType(null)
    upload.setShowUnsupportedModal(false)
    upload.setWaitlistEmail('')
    upload.setEmailSubmitted(false)
    resetAllReports()
    setCurrentOffer(null)
    disclaimer.setDisclaimerAccepted(false)
    disclaimer.setDisclaimerInput('')
    disclaimer.setPendingAnalysis(null)
  }

  // Rotate affiliate offers during loading
  useEffect(() => {
    if (!anyLoading || !upload.docType) return

    const offers = getOffersForDocType(upload.docType.document_type)
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
  }, [anyLoading, upload.docType])

  // Button text helper
  const getAnalyzeButtonText = () => {
    if (anyLoading) return '[ ANALYZING... ]'
    if (upload.classifying) return '[ READING... ]'
    if (upload.ocrLoading) return '[ EXTRACTING... ]'
    return '> CAN THEY FUCK ME?'
  }

  return (
    <div className={`app ${scanLines ? 'scanlines' : ''}`}>
      <Header
        isLoggedIn={auth.isLoggedIn}
        userEmail={auth.userEmail}
        openHistoryModal={auth.openHistoryModal}
        handleLogout={auth.handleLogout}
        setAuthMode={auth.setAuthMode}
        setShowAuthModal={auth.setShowAuthModal}
      />

      <main className="main">
        <InputSection
          getRootProps={upload.getRootProps}
          getInputProps={upload.getInputProps}
          isDragActive={upload.isDragActive}
          ocrLoading={upload.ocrLoading}
          classifying={upload.classifying}
          loading={anyLoading}
          uploadedFileName={upload.uploadedFileName}
          docType={upload.docType}
          docText={upload.docText}
          projectType={upload.projectType}
          selectedState={upload.selectedState}
          setDocText={upload.setDocText}
          setDocType={upload.setDocType}
          setProjectType={upload.setProjectType}
          setSelectedState={upload.setSelectedState}
          resetAll={resetAll}
          handleAnalyze={handleAnalyze}
          getAnalyzeButtonText={getAnalyzeButtonText}
        />

        {coi.report && <COIReport report={coi.report} tab={coi.tab} setTab={coi.setTab} />}
        {lease.report && <LeaseReport report={lease.report} tab={lease.tab} setTab={lease.setTab} />}
        {gym.report && <GymReport report={gym.report} tab={gym.tab} setTab={gym.setTab} />}
        {employment.report && <EmploymentReport report={employment.report} tab={employment.tab} setTab={employment.setTab} />}
        {freelancer.report && <FreelancerReport report={freelancer.report} tab={freelancer.tab} setTab={freelancer.setTab} />}
        {influencer.report && <InfluencerReport report={influencer.report} tab={influencer.tab} setTab={influencer.setTab} />}
        {timeshare.report && <TimeshareReport report={timeshare.report} tab={timeshare.tab} setTab={timeshare.setTab} />}
        {insurancePolicy.report && <InsurancePolicyReport_ report={insurancePolicy.report} tab={insurancePolicy.tab} setTab={insurancePolicy.setTab} />}
      </main>

      <DisclaimerModal
        show={disclaimer.showDisclaimerModal}
        disclaimerInput={disclaimer.disclaimerInput}
        onInputChange={disclaimer.setDisclaimerInput}
        onSubmit={disclaimer.handleDisclaimerSubmit}
        onCancel={disclaimer.handleDisclaimerCancel}
      />

      <UnsupportedModal
        show={upload.showUnsupportedModal}
        unsupportedType={upload.unsupportedType}
        waitlistEmail={upload.waitlistEmail}
        emailSubmitted={upload.emailSubmitted}
        onEmailChange={upload.setWaitlistEmail}
        onSubmit={handleWaitlistSubmit}
        onClose={() => upload.setShowUnsupportedModal(false)}
        onReset={resetAll}
      />

      <LoadingOverlay loading={anyLoading} currentOffer={currentOffer} />

      <AuthModal
        show={auth.showAuthModal}
        authMode={auth.authMode}
        authEmail={auth.authEmail}
        authPassword={auth.authPassword}
        authError={auth.authError}
        authLoading={auth.authLoading}
        onEmailChange={auth.setAuthEmail}
        onPasswordChange={auth.setAuthPassword}
        onLogin={auth.handleLogin}
        onSignup={auth.handleSignup}
        onClose={() => auth.setShowAuthModal(false)}
        onSwitchMode={auth.setAuthMode}
      />

      <HistoryModal
        show={auth.showHistoryModal}
        historyLoading={auth.historyLoading}
        userHistory={auth.userHistory}
        onClose={() => auth.setShowHistoryModal(false)}
      />

      <Footer donationText={donationText} STRIPE_DONATION_LINK={STRIPE_DONATION_LINK} />
    </div>
  )
}

export default App
