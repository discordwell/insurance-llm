import { useState } from 'react'

type AnalysisType = 'coi' | 'lease' | 'gym' | 'employment' | 'freelancer' | 'influencer' | 'timeshare' | 'insurance_policy'

interface UseDisclaimerOptions {
  runAnalysis: (docTypeStr: string | undefined) => Promise<void>
}

export function useDisclaimer({ runAnalysis }: UseDisclaimerOptions) {
  const [showDisclaimerModal, setShowDisclaimerModal] = useState(false)
  const [disclaimerInput, setDisclaimerInput] = useState('')
  const [disclaimerAccepted, setDisclaimerAccepted] = useState(false)
  const [pendingAnalysis, setPendingAnalysis] = useState<AnalysisType | null>(null)

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

  return {
    showDisclaimerModal,
    setShowDisclaimerModal,
    disclaimerInput,
    setDisclaimerInput,
    disclaimerAccepted,
    setDisclaimerAccepted,
    pendingAnalysis,
    setPendingAnalysis,
    handleDisclaimerSubmit,
    handleDisclaimerCancel,
  }
}
