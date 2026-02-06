interface LetterViewProps {
  text: string
  copyLabel: string
}

export default function LetterView({ text, copyLabel }: LetterViewProps) {
  return (
    <div className="letter-view">
      <div className="letter-content">
        <pre>{text}</pre>
      </div>
      <button
        className="pixel-btn secondary"
        onClick={() => navigator.clipboard.writeText(text)}
      >
        [COPY] {copyLabel}
      </button>
    </div>
  )
}
