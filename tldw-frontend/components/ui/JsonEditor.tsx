import React, { useCallback, useMemo, useRef, useState } from 'react';
import dynamic from 'next/dynamic';
import type { JsonSchema } from '@/lib/schema';

const Monaco = dynamic(() => import('@monaco-editor/react'), { ssr: false, loading: () => <div className="rounded border bg-gray-50 p-2 text-xs text-gray-500">Loading editor…</div> });

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
  const [fallback, setFallback] = useState(false);

  const handleEditorChange = useCallback((v?: string) => {
    onChange(v ?? '');
  }, [onChange]);

  const onMount = useCallback((editor: any, monaco: any) => {
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
        className="w-full rounded-md border-gray-300 bg-gray-50 font-mono text-sm shadow-sm focus:border-blue-500 focus:ring-blue-500"
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
      theme={theme as any}
      options={{
        readOnly: !!readOnly,
        minimap: { enabled: false },
        scrollBeyondLastLine: false,
        wordWrap: 'on',
        fontSize: 13,
      }}
      onMount={onMount}
      onError={() => setFallback(true)}
    />
  );
}

export default JsonEditor;
