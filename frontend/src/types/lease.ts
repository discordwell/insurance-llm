// Lease Analysis Types
export interface LeaseInsuranceClause {
  clause_type: string
  original_text: string
  summary: string
  risk_level: 'high' | 'medium' | 'low'
  explanation: string
  recommendation: string
}

export interface LeaseRedFlag {
  name: string
  severity: 'critical' | 'warning' | 'info'
  clause_text?: string
  explanation: string
  protection: string
}

export interface LeaseAnalysisReport {
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
