import type { AffiliateOffer } from '../config/affiliates'

interface LoadingOverlayProps {
  loading: boolean
  currentOffer: AffiliateOffer | null
}

export default function LoadingOverlay({ loading, currentOffer }: LoadingOverlayProps) {
  if (!loading) return null

  return (
    <div className="loading-overlay">
      <div className="loading-content">
        <div className="loading-spinner">
          <div className="spinner-pixel"></div>
        </div>
        <h2 className="loading-title">ANALYZING YOUR DOCUMENT...</h2>
        <p className="loading-subtitle">This usually takes 10-15 seconds</p>

        {/* Affiliate Offer */}
        {currentOffer && (
          <div className="affiliate-card">
            <div className="affiliate-badge">WHILE YOU WAIT</div>
            <h3 className="affiliate-name">{currentOffer.name}</h3>
            <p className="affiliate-tagline">{currentOffer.tagline}</p>
            <p className="affiliate-description">{currentOffer.description}</p>
            <a
              href={currentOffer.url}
              target="_blank"
              rel="noopener noreferrer"
              className="affiliate-cta"
              onClick={() => {
                // Track click (would be analytics in production)
                console.log('Affiliate click:', currentOffer.id)
              }}
            >
              {currentOffer.cta} &rarr;
            </a>
          </div>
        )}
      </div>
    </div>
  )
}
