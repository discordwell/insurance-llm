export const getStatusColor = (status: string) => {
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

export const getStatusLabel = (status: string) => {
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

export const getRiskColor = (risk: string) => {
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

export const getRiskLabel = (risk: string) => {
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
