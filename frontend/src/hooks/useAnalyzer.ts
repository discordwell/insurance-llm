import { useState } from 'react'
import { API_BASE } from '../services/api'

interface AnalyzerConfig {
  endpoint: string
  buildBody: () => Record<string, unknown>
  errorMessage: string
}

export function useAnalyzer<T>(authToken: string | null) {
  const [report, setReport] = useState<T | null>(null)
  const [tab, setTab] = useState<'report' | 'letter'>('report')
  const [loading, setLoading] = useState(false)

  const analyze = async (config: AnalyzerConfig) => {
    setLoading(true)
    setReport(null)
    try {
      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      if (authToken) headers['Authorization'] = `Bearer ${authToken}`
      const res = await fetch(`${API_BASE}${config.endpoint}`, {
        method: 'POST',
        headers,
        body: JSON.stringify(config.buildBody())
      })
      if (!res.ok) throw new Error(config.errorMessage)
      const data = await res.json()
      setReport(data)
      setTab('report')
    } catch (err) {
      console.error(err)
      alert(config.errorMessage + ' Make sure the backend is running!')
    } finally {
      setLoading(false)
    }
  }

  const reset = () => {
    setReport(null)
    setTab('report')
  }

  return { report, tab, setTab, loading, analyze, reset }
}
