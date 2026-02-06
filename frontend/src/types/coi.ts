// COI Compliance Types
export interface COIData {
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

export interface ComplianceRequirement {
  name: string
  required_value: string
  actual_value: string
  status: 'pass' | 'fail' | 'warning'
  explanation: string
}

// Extraction confidence metadata
export interface ExtractionMetadata {
  overall_confidence: number  // 0-1
  needs_human_review: boolean
  review_reasons: string[]
  low_confidence_fields: string[]
  extraction_notes?: string
}

export interface ComplianceReport {
  overall_status: 'compliant' | 'non-compliant' | 'needs-review'
  coi_data: COIData
  critical_gaps: ComplianceRequirement[]
  warnings: ComplianceRequirement[]
  passed: ComplianceRequirement[]
  risk_exposure: string
  fix_request_letter: string
  extraction_metadata?: ExtractionMetadata
}
