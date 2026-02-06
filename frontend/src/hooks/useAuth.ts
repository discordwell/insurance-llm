import { useState, useEffect } from 'react'
import { API_BASE } from '../services/api'

export interface UserHistoryEntry {
  id: number
  created_at: string
  document_type: string
  overall_risk: string
  risk_score: number
}

export function useAuth() {
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
  const [userHistory, setUserHistory] = useState<UserHistoryEntry[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)

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

  return {
    // Auth state
    isLoggedIn,
    userEmail,
    authToken,
    showAuthModal,
    setShowAuthModal,
    authMode,
    setAuthMode,
    authEmail,
    setAuthEmail,
    authPassword,
    setAuthPassword,
    authError,
    setAuthError,
    authLoading,

    // History state
    showHistoryModal,
    setShowHistoryModal,
    userHistory,
    historyLoading,

    // Auth handlers
    handleSignup,
    handleLogin,
    handleLogout,
    fetchHistory,
    openHistoryModal,
  }
}
