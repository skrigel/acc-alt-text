import { useState } from 'react'
import './App.css'

interface ExtractedContext {
  title?: string
  sectionHeading?: string
  nearbyText?: string
  figureCaption?: string
}

interface GeneratedDescription {
  short: string
  long?: string
}

interface VisualizationResult {
  svgContent: string
  context: ExtractedContext
  description: GeneratedDescription
}

function App() {
  const [url, setUrl] = useState('')
  const [descriptionType, setDescriptionType] = useState<'short' | 'both'>('short')
  const [isProcessing, setIsProcessing] = useState(false)
  const [results, setResults] = useState<VisualizationResult[]>([])
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsProcessing(true)
    setError(null)

    try {
      const response = await fetch('http://localhost:8000/api/generate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          url,
          description_type: descriptionType
        })
      })

      if (!response.ok) {
        throw new Error('Failed to process URL')
      }

      const data = await response.json()
      setResults(data.visualizations || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setIsProcessing(false)
    }
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
  }

  return (
    <div className="container">
      <header className="header">
        <h1>
          <span className="title-sub">Chart Description Generator</span>
        </h1>
        <p className="subtitle">
          WCAG-compliant alt-text for SVG data visualizations
        </p>
      </header>

      <main className="main">
        <form onSubmit={handleSubmit} className="input-section">
          <div className="form-group">
            <label htmlFor="url-input" className="label">
              Webpage URL
            </label>
            <div className="input-wrapper">
              <input
                id="url-input"
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://example.com/article-with-charts"
                className="url-input"
                required
                disabled={isProcessing}
              />
              <div className="input-decoration"></div>
            </div>
          </div>

          <div className="form-group">
            <label className="label">Description Scope</label>
            <div className="radio-group">
              <label className={`radio-option ${descriptionType === 'short' ? 'active' : ''}`}>
                <input
                  type="radio"
                  name="description-type"
                  value="short"
                  checked={descriptionType === 'short'}
                  onChange={(e) => setDescriptionType(e.target.value as 'short' | 'both')}
                  disabled={isProcessing}
                />
                <span className="radio-label">
                  <span className="radio-title">Short Description</span>
                  <span className="radio-desc">Concise alt attribute value</span>
                </span>
              </label>
              <label className={`radio-option ${descriptionType === 'both' ? 'active' : ''}`}>
                <input
                  type="radio"
                  name="description-type"
                  value="both"
                  checked={descriptionType === 'both'}
                  onChange={(e) => setDescriptionType(e.target.value as 'short' | 'both')}
                  disabled={isProcessing}
                />
                <span className="radio-label">
                  <span className="radio-title">Short + Long</span>
                  <span className="radio-desc">With detailed aria-describedby</span>
                </span>
              </label>
            </div>
          </div>

          <button
            type="submit"
            className="submit-btn"
            disabled={isProcessing || !url}
          >
            {isProcessing ? (
              <>
                <span className="spinner"></span>
                Processing...
              </>
            ) : (
              'Generate Descriptions'
            )}
          </button>
        </form>

        {error && (
          <div className="error-message">
            <div className="error-icon">!</div>
            <p>{error}</p>
          </div>
        )}

        {results.length > 0 && (
          <div className="results-section">
            <div className="results-header">
              <h2>Generated Descriptions</h2>
              <span className="results-count">{results.length} visualization{results.length !== 1 ? 's' : ''} found</span>
            </div>

            {results.map((result, index) => (
              <article key={index} className="result-card">
                <div className="result-grid">
                  <div className="result-visual">
                    <h3 className="section-title">Extracted Visualization</h3>
                    <div
                      className="svg-preview"
                      dangerouslySetInnerHTML={{ __html: result.svgContent }}
                    />
                  </div>

                  <div className="result-context">
                    <h3 className="section-title">Page Context</h3>
                    <dl className="context-list">
                      {result.context.title && (
                        <>
                          <dt>Page Title</dt>
                          <dd>{result.context.title}</dd>
                        </>
                      )}
                      {result.context.sectionHeading && (
                        <>
                          <dt>Section Heading</dt>
                          <dd>{result.context.sectionHeading}</dd>
                        </>
                      )}
                      {result.context.figureCaption && (
                        <>
                          <dt>Figure Caption</dt>
                          <dd>{result.context.figureCaption}</dd>
                        </>
                      )}
                      {result.context.nearbyText && (
                        <>
                          <dt>Nearby Text</dt>
                          <dd className="nearby-text">{result.context.nearbyText}</dd>
                        </>
                      )}
                    </dl>
                  </div>
                </div>

                <div className="result-descriptions">
                  <div className="description-block">
                    <div className="description-header">
                      <h4>Short Description</h4>
                      <button
                        onClick={() => copyToClipboard(result.description.short)}
                        className="copy-btn"
                        title="Copy to clipboard"
                      >
                        Copy
                      </button>
                    </div>
                    <div className="description-content short">
                      <code>{result.description.short}</code>
                    </div>
                    <p className="description-meta">For alt attribute</p>
                  </div>

                  {result.description.long && (
                    <div className="description-block">
                      <div className="description-header">
                        <h4>Long Description</h4>
                        <button
                          onClick={() => copyToClipboard(result.description.long!)}
                          className="copy-btn"
                          title="Copy to clipboard"
                        >
                          Copy
                        </button>
                      </div>
                      <div className="description-content long">
                        <p>{result.description.long}</p>
                      </div>
                      <p className="description-meta">For aria-describedby or figcaption</p>
                    </div>
                  )}
                </div>
              </article>
            ))}
          </div>
        )}

        {!isProcessing && results.length === 0 && !error && (
          <div className="empty-state">
            <div className="empty-icon">
              <svg width="64" height="64" viewBox="0 0 64 64" fill="none">
                <rect x="8" y="16" width="48" height="36" rx="2" stroke="currentColor" strokeWidth="2"/>
                <path d="M16 36L24 28L32 32L40 24L48 28" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                <circle cx="20" cy="24" r="2" fill="currentColor"/>
              </svg>
            </div>
            <h3>Ready to Generate</h3>
            <p>Enter a webpage URL to extract SVG visualizations and generate WCAG-compliant descriptions</p>
          </div>
        )}
      </main>

      <footer className="footer">
        <div className="footer-content">
          <p>Built to improve web accessibility • Following WAI-ARIA guidelines</p>
        </div>
      </footer>
    </div>
  )
}

export default App