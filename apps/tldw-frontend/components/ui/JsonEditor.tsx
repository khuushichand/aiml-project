import React, { useCallback, useState } from 'react';
import dynamic from 'next/dynamic';
import type { JsonSchema } from '@web/lib/schema';

const Monaco = dynamic(() => import('@monaco-editor/react'), { ssr: false, loading: () => <div className="rounded border bg-bg p-2 text-xs text-text-muted">Loading editor…</div> });

export function JsonEditor({
  value,
  onChange,
  height = 260,
  schema,
  readOnly,
}: {
  value: string;
  onChange: (val: string) => void;
  height?: number | string;
  schema?: JsonSchema;
  readOnly?: boolean;
}) {
  const [fallback] = useState(false);

  const handleEditorChange = useCallback((v?: string) => {
    onChange(v ?? '');
  }, [onChange]);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const onMount = useCallback((editor: unknown, monaco: any) => {
    try {
      if (schema && monaco?.languages?.json?.jsonDefaults) {
        monaco.languages.json.jsonDefaults.setDiagnosticsOptions({
          validate: true,
          allowComments: true,
          enableSchemaRequest: false,
          schemas: [
            {
              uri: 'inmemory://model/schema.json',
              fileMatch: ['*'],
              schema,
            },
          ],
        });
      }
    } catch {
      // ignore
    }
  }, [schema]);

  if (fallback) {
    return (
      <textarea
        className="w-full rounded-md border-border bg-bg font-mono text-sm shadow-sm focus:border-primary focus:ring-primary"
        style={{ height }}
        value={value}
        readOnly={readOnly}
        onChange={(e) => onChange(e.target.value)}
      />
    );
  }

  const theme = (typeof document !== 'undefined' && document.documentElement.classList.contains('theme-dark')) ? 'vs-dark' : 'light';
  return (
    <Monaco
      defaultLanguage="json"
      value={value}
      onChange={handleEditorChange}
      height={height}
      theme={theme as string}
      options={{
        readOnly: !!readOnly,
        minimap: { enabled: false },
        scrollBeyondLastLine: false,
        wordWrap: 'on',
        fontSize: 13,
      }}
      onMount={onMount}
    />
  );
}

export default JsonEditor;
