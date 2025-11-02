import React, { useMemo } from 'react';

function escapeHtml(unsafe: string) {
  return unsafe
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/\n/g, '<br/>')
    .replace(/\t/g, '&nbsp;&nbsp;&nbsp;&nbsp;')
    .replace(/\s/g, '&nbsp;');
}

function syntaxHighlightJson(json: string): string {
  const esc = escapeHtml(json);
  return esc
    // keys
    .replace(/(&quot;)([^&]*?)(&quot;)(\s*:\s*)/g, '<span class="json-string">$1</span><span class="json-key">$2</span><span class="json-string">$3</span>$4')
    // strings
    .replace(/(&quot;.*?&quot;)/g, '<span class="json-string">$1</span>')
    // numbers
    .replace(/\b(-?\d+(?:\.\d+)?)\b/g, '<span class="json-number">$1</span>')
    // booleans
    .replace(/\b(true|false)\b/g, '<span class="json-boolean">$1</span>')
    // null
    .replace(/\bnull\b/g, '<span class="json-null">null</span>');
}

export interface JsonViewerProps {
  data: any;
  className?: string;
  highlight?: boolean;
}

export function JsonViewer({ data, className, highlight = true }: JsonViewerProps) {
  const pretty = useMemo(() => {
    try { return JSON.stringify(data, null, 2); } catch { return String(data); }
  }, [data]);

  if (!highlight) {
    return (
      <pre className={`overflow-auto whitespace-pre-wrap break-words font-mono text-sm ${className || ''}`}>{pretty}</pre>
    );
  }

  const html = useMemo(() => syntaxHighlightJson(pretty), [pretty]);
  return (
    <pre className={`overflow-auto whitespace-pre-wrap break-words font-mono text-sm ${className || ''}`} dangerouslySetInnerHTML={{ __html: html }} />
  );
}

export default JsonViewer;
