// Generic RedFlag type used by new contract types
export interface ContractRedFlag {
  name: string
  severity: 'critical' | 'warning' | 'info'
  clause_text?: string
  explanation: string
  protection: string
}

// Gym Contract Types
export interface GymContractReport {
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
export interface EmploymentContractReport {
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
export interface FreelancerContractReport {
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
export interface InfluencerContractReport {
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
export interface TimeshareContractReport {
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
export interface InsurancePolicyRedFlag {
  name: string
  severity: 'critical' | 'warning' | 'info'
  clause_text?: string
  explanation: string
  what_to_ask: string
}

export interface InsurancePolicyReport {
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
