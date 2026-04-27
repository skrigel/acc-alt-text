import { useState, useCallback } from 'react'
import { type SvgResult }from './constants'
import parse from 'html-react-parser';

interface ResultsModalProps {
  results: SvgResult[]
}

export function ResultsModal({ results }: ResultsModalProps) {
  const [current, setCurrent] = useState(0)
  const [copied, setCopied] = useState<'short' | 'long' | null>(null)
  const [sliding, setSliding] = useState<'left' | 'right' | null>(null)

  const go = useCallback((dir: 'prev' | 'next') => {
    setSliding(dir === 'next' ? 'left' : 'right')
    setTimeout(() => {
      setCurrent(c =>
        dir === 'next' ? Math.min(c + 1, results.length - 1) : Math.max(c - 1, 0)
      )
      setSliding(null)
    }, 180)
  }, [results.length])

  const copy = (text: string, which: 'short' | 'long') => {
    navigator.clipboard.writeText(text)
    setCopied(which)
    setTimeout(() => setCopied(null), 1800)
  }

  if (results.length === 0) return null

  const item: SvgResult = results[current]

  console.log("raw,", item.raw)

  return (
    <>
      <style>{`
        .rs-section {
          margin-top: 48px;
          animation: fadeInUp 0.6s ease-out 0.3s both;
        }

        .rs-header {
          display: flex;
          align-items: baseline;
          justify-content: space-between;
          margin-bottom: 32px;
          padding-bottom: 16px;
          border-bottom: 2px solid var(--border-primary);
        }

        .rs-header h2 {
          font-family: var(--font-display);
          font-weight: 700;
          font-size: 32px;
          color: var(--text-primary);
          margin: 0;
          letter-spacing: -0.01em;
        }

        .rs-count {
          font-family: var(--font-mono);
          font-size: 14px;
          color: var(--text-secondary);
          background: var(--bg-elevated);
          padding: 6px 12px;
          border-radius: 6px;
          border: 1px solid var(--border-primary);
        }

        .rs-card {
          background: var(--bg-elevated);
          border: 2px solid var(--border-primary);
          border-radius: 12px;
          padding: 40px;
          box-shadow:
            0 1px 3px rgba(26, 58, 52, 0.06),
            0 8px 24px rgba(26, 58, 52, 0.04);
          overflow: hidden;
        }

        .rs-slide {
          transition: transform 0.18s ease, opacity 0.18s ease;
        }
        .rs-slide.exit-left  { transform: translateX(-20px); opacity: 0; pointer-events: none; }
        .rs-slide.exit-right { transform: translateX(20px);  opacity: 0; pointer-events: none; }

        .rs-index {
          font-family: var(--font-mono);
          font-size: 13px;
          color: var(--text-secondary);
          background: var(--bg-primary);
          border: 1px solid var(--border-secondary);
          border-radius: 6px;
          padding: 4px 10px;
          display: inline-block;
          margin-bottom: 28px;
          letter-spacing: 0.04em;
        }

        .rs-descriptions {
          display: flex;
          flex-direction: column;
          gap: 24px;
        }

        .rs-block {
          background: var(--bg-primary);
          border: 2px solid var(--border-secondary);
          border-radius: 8px;
          padding: 24px;
        }

        .rs-block-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 16px;
        }

        .rs-block-header h4 {
          font-family: var(--font-display);
          font-weight: 600;
          font-size: 16px;
          color: var(--text-primary);
          margin: 0;
        }

        .rs-copy-btn {
          font-family: var(--font-body);
          font-size: 13px;
          font-weight: 500;
          padding: 6px 12px;
          border: 1px solid var(--border-primary);
          border-radius: 6px;
          background: var(--bg-elevated);
          color: var(--text-secondary);
          cursor: pointer;
          transition: all 0.2s ease;
        }
        .rs-copy-btn:hover {
          background: var(--accent-primary);
          color: var(--bg-primary);
          border-color: var(--accent-primary);
        }
        .rs-copy-btn.copied {
          background: var(--accent-primary);
          color: var(--bg-primary);
          border-color: var(--accent-primary);
        }

        .rs-short-text {
          font-family: var(--font-mono);
          font-size: 14px;
          color: var(--text-primary);
          background: var(--bg-elevated);
          padding: 12px 16px;
          border-radius: 6px;
          display: block;
          border-left: 4px solid var(--accent-primary);
          margin-bottom: 12px;
          line-height: 1.6;
        }

        .rs-long-text {
          font-family: var(--font-body);
          font-size: 15px;
          color: var(--text-primary);
          margin: 0 0 12px;
          padding-left: 16px;
          border-left: 4px solid var(--accent-secondary);
          line-height: 1.6;
        }

        .rs-meta {
          font-family: var(--font-mono);
          font-size: 12px;
          color: var(--text-tertiary);
          margin: 0;
        }

        .rs-nav {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-top: 32px;
          padding-top: 28px;
          border-top: 2px solid var(--border-secondary);
        }

        .rs-nav-btn {
          font-family: var(--font-display);
          font-weight: 600;
          font-size: 15px;
          padding: 10px 20px;
          border: 2px solid var(--border-primary);
          border-radius: 8px;
          background: var(--bg-primary);
          color: var(--text-secondary);
          cursor: pointer;
          transition: all 0.2s ease;
        }
        .rs-nav-btn:hover:not(:disabled) {
          border-color: var(--accent-primary);
          color: var(--accent-primary);
        }
        .rs-nav-btn:disabled {
          opacity: 0.3;
          cursor: default;
        }

        .rs-dots {
          display: flex;
          gap: 8px;
          align-items: center;
        }

        .rs-dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: var(--border-primary);
          border: none;
          padding: 0;
          cursor: pointer;
          transition: all 0.2s ease;
        }
        .rs-dot.active {
          background: var(--accent-primary);
          width: 22px;
          border-radius: 4px;
        }
      `}</style>

      <div className="rs-section">
        <div className="rs-header">
          <h2>Generated Descriptions</h2>
          <span className="rs-count">
            {results.length} visualization{results.length !== 1 ? 's' : ''} found
          </span>
        </div>

        <div className="rs-card">
          <div className={`rs-slide${sliding === 'left' ? ' exit-left' : sliding === 'right' ? ' exit-right' : ''}`}>

            <span className="rs-index">
              visualization {current + 1} of {results.length} · {item.type ? item.type.toUpperCase() : 'SVG'}
            </span>
            <div>
              
              {parse(item.raw)}
            </div>
            <div className="rs-descriptions">
              <div className="rs-block">
                <div className="rs-block-header">
                  <h4>Short Description</h4>
                  <button
                    className={`rs-copy-btn${copied === 'short' ? ' copied' : ''}`}
                    onClick={() => copy(item.short_description, 'short')}
                  >
                    {copied === 'short' ? 'Copied!' : 'Copy'}
                  </button>
                </div>
                <code className="rs-short-text">{item.short_description}</code>
                <p className="rs-meta">For alt attribute</p>
              </div>

              {item.long_description && (
                <div className="rs-block">
                  <div className="rs-block-header">
                    <h4>Long Description</h4>
                    <button
                      className={`rs-copy-btn${copied === 'long' ? ' copied' : ''}`}
                      onClick={() => copy(item.long_description, 'long')}
                    >
                      {copied === 'long' ? 'Copied!' : 'Copy'}
                    </button>
                  </div>
                  <p className="rs-long-text">{item.long_description}</p>
                  <p className="rs-meta">For aria-describedby or figcaption</p>
                </div>
              )}
            </div>

          </div>

          {results.length > 1 && (
            <div className="rs-nav">
              <button
                className="rs-nav-btn"
                onClick={() => go('prev')}
                disabled={current === 0}
              >
                ← Previous
              </button>

              <div className="rs-dots">
                {results.map((_, i) => (
                  <button
                    key={i}
                    className={`rs-dot${i === current ? ' active' : ''}`}
                    onClick={() => setCurrent(i)}
                    aria-label={`Go to visualization ${i + 1}`}
                  />
                ))}
              </div>

              <button
                className="rs-nav-btn"
                onClick={() => go('next')}
                disabled={current === results.length - 1}
              >
                Next →
              </button>
            </div>
          )}
        </div>
      </div>
    </>
  )
}