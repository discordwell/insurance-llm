// Document classification result
export interface ClassifyResult {
  document_type: 'coi' | 'lease' | 'gym' | 'timeshare' | 'influencer' | 'freelancer' | 'employment' | 'insurance_policy' | 'contract' | 'unknown'
  confidence: number
  description: string
  supported: boolean
}
