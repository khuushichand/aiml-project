import React, { useCallback, useState } from "react"
import { Page } from "react-pdf"
import { Spin } from "antd"
import { PageNoteButton } from "../PageNoteButton"

// Note: react-pdf text/annotation layer styles should be imported at the app level
// In Next.js: add to pages/_app.tsx or use next.config.js transpilePackages

interface PdfPageProps {
  pageNumber: number
  scale: number
  onSetRef?: (element: HTMLDivElement | null) => void
  /** Hide the page note button (e.g., in thumbnail view) */
  hidePageNote?: boolean
}

export const PdfPage: React.FC<PdfPageProps> = ({
  pageNumber,
  scale,
  onSetRef,
  hidePageNote = false
}) => {
  const [loading, setLoading] = useState(true)

  const handleRenderSuccess = useCallback(() => {
    setLoading(false)
  }, [])

  const handleRenderError = useCallback(() => {
    setLoading(false)
  }, [])

  return (
    <div
      ref={onSetRef}
      data-page-number={pageNumber}
      className="group relative bg-white shadow-lg"
    >
      {loading && (
        <div className="absolute inset-0 z-10 flex items-center justify-center bg-white/80">
          <Spin size="small" />
        </div>
      )}
      {/* Page note button - appears on hover */}
      {!hidePageNote && !loading && (
        <PageNoteButton pageNumber={pageNumber} />
      )}
      <Page
        pageNumber={pageNumber}
        scale={scale}
        onRenderSuccess={handleRenderSuccess}
        onRenderError={handleRenderError}
        loading=""
        renderTextLayer={true}
        renderAnnotationLayer={true}
        className="pdf-page"
      />
    </div>
  )
}

export default PdfPage
