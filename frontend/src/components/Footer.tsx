interface FooterProps {
  donationText: { text: string; isHtml: boolean }
  STRIPE_DONATION_LINK: string
}

export default function Footer({ donationText, STRIPE_DONATION_LINK }: FooterProps) {
  return (
    <footer className="footer">
      <a
        href={STRIPE_DONATION_LINK}
        target="_blank"
        rel="noopener noreferrer"
        className="donate-link-footer"
      >
        {donationText.isHtml ? (
          <span dangerouslySetInnerHTML={{ __html: donationText.text }} />
        ) : (
          donationText.text
        )}
      </a>
      <a
        href="https://github.com/discordwell/cantheyfuckme"
        target="_blank"
        rel="noopener noreferrer"
        className="github-link-small"
      >
        github
      </a>
    </footer>
  )
}
