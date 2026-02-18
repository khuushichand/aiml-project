import * as React from "react"
import { cn } from "@/lib/utils"

type TableProps = React.TableHTMLAttributes<HTMLTableElement> & {
  caption?: string
  captionContext?: string
  captionClassName?: string
}

const isNamedComponent = (nodeType: unknown, displayName: string): boolean => {
  if (!nodeType || typeof nodeType === 'string') return false
  if (typeof nodeType === 'function') {
    return (nodeType as { displayName?: string }).displayName === displayName
  }
  if (typeof nodeType === 'object') {
    return (nodeType as { displayName?: string }).displayName === displayName
  }
  return false
}

const extractTextContent = (node: React.ReactNode): string => {
  if (typeof node === 'string' || typeof node === 'number') {
    return String(node).trim()
  }

  if (Array.isArray(node)) {
    return node
      .map((item) => extractTextContent(item))
      .filter(Boolean)
      .join(' ')
      .replace(/\s+/g, ' ')
      .trim()
  }

  if (!React.isValidElement(node)) {
    return ''
  }

  return extractTextContent((node.props as { children?: React.ReactNode }).children)
}

const containsCaptionNode = (nodes: React.ReactNode): boolean => {
  let found = false
  React.Children.forEach(nodes, (node) => {
    if (found || !React.isValidElement(node)) return
    const type = node.type
    if (type === 'caption' || isNamedComponent(type, 'TableCaption')) {
      found = true
      return
    }
    if (containsCaptionNode((node.props as { children?: React.ReactNode }).children)) {
      found = true
    }
  })
  return found
}

const countBodyRows = (nodes: React.ReactNode, inBody = false): number => {
  let total = 0
  React.Children.forEach(nodes, (node) => {
    if (!React.isValidElement(node)) return
    const type = node.type
    const isBody = type === 'tbody' || isNamedComponent(type, 'TableBody')
    const isRow = type === 'tr' || isNamedComponent(type, 'TableRow')
    const nextInBody = inBody || isBody
    if (isRow && nextInBody) {
      total += 1
    }
    total += countBodyRows((node.props as { children?: React.ReactNode }).children, nextInBody)
  })
  return total
}

const extractHeaders = (nodes: React.ReactNode): string[] => {
  const labels: string[] = []
  React.Children.forEach(nodes, (node) => {
    if (!React.isValidElement(node)) return
    const type = node.type
    const isHeader = type === 'th' || isNamedComponent(type, 'TableHead')
    if (isHeader) {
      const label = extractTextContent((node.props as { children?: React.ReactNode }).children)
      if (label) labels.push(label)
    }
    labels.push(...extractHeaders((node.props as { children?: React.ReactNode }).children))
  })
  return labels
}

const Table = React.forwardRef<HTMLTableElement, TableProps>(
  ({ className, caption, captionContext, captionClassName, children, ...props }, ref) => {
    const scrollContainerRef = React.useRef<HTMLDivElement>(null)
    const tableRef = React.useRef<HTMLTableElement>(null)
    const [showLeftShadow, setShowLeftShadow] = React.useState(false)
    const [showRightShadow, setShowRightShadow] = React.useState(false)
    const hasCaptionChild = React.useMemo(() => containsCaptionNode(children), [children])
    const bodyRowCount = React.useMemo(() => countBodyRows(children), [children])
    const headerLabels = React.useMemo(() => extractHeaders(children), [children])
    const computedCaption = React.useMemo(() => {
      if (hasCaptionChild) return null
      if (caption) return caption
      const rowLabel = `${bodyRowCount} row${bodyRowCount === 1 ? '' : 's'}`
      if (captionContext && captionContext.trim()) {
        return `${captionContext.trim()} table with ${rowLabel}.`
      }
      if (headerLabels.length > 0) {
        return `Table columns: ${headerLabels.join(', ')}. ${rowLabel}.`
      }
      return `Data table with ${rowLabel}.`
    }, [bodyRowCount, caption, captionContext, hasCaptionChild, headerLabels])

    React.useImperativeHandle(ref, () => tableRef.current as HTMLTableElement, [])

    const updateScrollShadows = React.useCallback(() => {
      const container = scrollContainerRef.current
      if (!container) {
        setShowLeftShadow(false)
        setShowRightShadow(false)
        return
      }

      const hasOverflow = container.scrollWidth - container.clientWidth > 1
      if (!hasOverflow) {
        setShowLeftShadow(false)
        setShowRightShadow(false)
        return
      }

      setShowLeftShadow(container.scrollLeft > 1)
      setShowRightShadow(container.scrollLeft + container.clientWidth < container.scrollWidth - 1)
    }, [])

    React.useEffect(() => {
      const container = scrollContainerRef.current
      if (!container) return

      updateScrollShadows()
      container.addEventListener('scroll', updateScrollShadows, { passive: true })
      window.addEventListener('resize', updateScrollShadows)

      let observer: ResizeObserver | null = null
      if (typeof ResizeObserver !== 'undefined') {
        observer = new ResizeObserver(() => {
          updateScrollShadows()
        })
        observer.observe(container)
        if (tableRef.current) observer.observe(tableRef.current)
      }

      return () => {
        container.removeEventListener('scroll', updateScrollShadows)
        window.removeEventListener('resize', updateScrollShadows)
        observer?.disconnect()
      }
    }, [updateScrollShadows])

    return (
      <div ref={scrollContainerRef} className="relative w-full overflow-auto" data-testid="table-scroll-container">
        {showLeftShadow && (
          <div
            aria-hidden="true"
            data-testid="table-scroll-shadow-left"
            className="pointer-events-none absolute inset-y-0 left-0 z-10 w-6 bg-gradient-to-r from-background via-background/80 to-transparent"
          />
        )}
        {showRightShadow && (
          <div
            aria-hidden="true"
            data-testid="table-scroll-shadow-right"
            className="pointer-events-none absolute inset-y-0 right-0 z-10 w-6 bg-gradient-to-l from-background via-background/80 to-transparent"
          />
        )}
        <table
          ref={tableRef}
          className={cn("w-full caption-bottom text-sm", className)}
          {...props}
        >
          {computedCaption ? <caption className={cn("sr-only", captionClassName)}>{computedCaption}</caption> : null}
          {children}
        </table>
      </div>
    )
  }
)
Table.displayName = "Table"

const TableHeader = React.forwardRef<HTMLTableSectionElement, React.HTMLAttributes<HTMLTableSectionElement>>(
  ({ className, ...props }, ref) => (
    <thead
      ref={ref}
      className={cn("sticky top-0 z-10 bg-background [&_tr]:border-b", className)}
      {...props}
    />
  )
)
TableHeader.displayName = "TableHeader"

const TableBody = React.forwardRef<HTMLTableSectionElement, React.HTMLAttributes<HTMLTableSectionElement>>(
  ({ className, ...props }, ref) => (
    <tbody
      ref={ref}
      className={cn("[&_tr:last-child]:border-0", className)}
      {...props}
    />
  )
)
TableBody.displayName = "TableBody"

const TableFooter = React.forwardRef<HTMLTableSectionElement, React.HTMLAttributes<HTMLTableSectionElement>>(
  ({ className, ...props }, ref) => (
    <tfoot
      ref={ref}
      className={cn("border-t bg-muted/50 font-medium [&>tr]:last:border-b-0", className)}
      {...props}
    />
  )
)
TableFooter.displayName = "TableFooter"

const TableRow = React.forwardRef<HTMLTableRowElement, React.HTMLAttributes<HTMLTableRowElement>>(
  ({ className, ...props }, ref) => (
    <tr
      ref={ref}
      className={cn(
        "border-b transition-colors hover:bg-muted/50 data-[state=selected]:bg-muted",
        className
      )}
      {...props}
    />
  )
)
TableRow.displayName = "TableRow"

const TableHead = React.forwardRef<HTMLTableCellElement, React.ThHTMLAttributes<HTMLTableCellElement>>(
  ({ className, ...props }, ref) => (
    <th
      ref={ref}
      className={cn(
        "h-12 px-4 text-left align-middle font-medium text-muted-foreground [&:has([role=checkbox])]:pr-0",
        className
      )}
      {...props}
    />
  )
)
TableHead.displayName = "TableHead"

const TableCell = React.forwardRef<HTMLTableCellElement, React.TdHTMLAttributes<HTMLTableCellElement>>(
  ({ className, ...props }, ref) => (
    <td
      ref={ref}
      className={cn("p-4 align-middle [&:has([role=checkbox])]:pr-0", className)}
      {...props}
    />
  )
)
TableCell.displayName = "TableCell"

const TableCaption = React.forwardRef<HTMLTableCaptionElement, React.HTMLAttributes<HTMLTableCaptionElement>>(
  ({ className, ...props }, ref) => (
    <caption
      ref={ref}
      className={cn("mt-4 text-sm text-muted-foreground", className)}
      {...props}
    />
  )
)
TableCaption.displayName = "TableCaption"

export {
  Table,
  TableHeader,
  TableBody,
  TableFooter,
  TableHead,
  TableRow,
  TableCell,
  TableCaption,
}
