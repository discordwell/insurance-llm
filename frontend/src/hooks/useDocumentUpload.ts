import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { API_BASE } from '../services/api'
import type { ClassifyResult } from '../types'

interface UseDocumentUploadOptions {
  onReportsReset: () => void
}

export function useDocumentUpload({ onReportsReset }: UseDocumentUploadOptions) {
  const [loading, setLoading] = useState(false)
  const [ocrLoading, setOcrLoading] = useState(false)
  const [classifying, setClassifying] = useState(false)
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null)

  // Document state
  const [docText, setDocText] = useState('')
  const [docType, setDocType] = useState<ClassifyResult | null>(null)
  const [projectType, setProjectType] = useState('commercial_construction')
  const [selectedState, setSelectedState] = useState('')

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

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    const file = acceptedFiles[0]
    if (!file) return

    setUploadedFileName(file.name)
    onReportsReset()
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

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'image/*': ['.png', '.jpg', '.jpeg', '.gif', '.webp'],
      'text/plain': ['.txt']
    },
    multiple: false
  })

  const getAnalyzeButtonText = () => {
    if (loading) return '[ ANALYZING... ]'
    if (classifying) return '[ READING... ]'
    if (ocrLoading) return '[ EXTRACTING... ]'
    return '> CAN THEY FUCK ME?'
  }

  return {
    // Loading states
    loading,
    setLoading,
    ocrLoading,
    classifying,

    // Document state
    uploadedFileName,
    setUploadedFileName,
    docText,
    setDocText,
    docType,
    setDocType,
    projectType,
    setProjectType,
    selectedState,
    setSelectedState,

    // Unsupported document modal
    showUnsupportedModal,
    setShowUnsupportedModal,
    unsupportedType,
    setUnsupportedType,
    waitlistEmail,
    setWaitlistEmail,
    emailSubmitted,
    setEmailSubmitted,

    // Functions
    classifyDocument,
    handleClassification,

    // Dropzone
    getRootProps,
    getInputProps,
    isDragActive,

    // Button text
    getAnalyzeButtonText,
  }
}
