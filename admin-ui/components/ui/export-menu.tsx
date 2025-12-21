'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Download, FileSpreadsheet, FileJson, ChevronDown } from 'lucide-react';
import { ExportFormat } from '@/lib/export';

interface ExportMenuProps {
  onExport: (format: ExportFormat) => void;
  disabled?: boolean;
  label?: string;
}

export function ExportMenu({ onExport, disabled = false, label = 'Export' }: ExportMenuProps) {
  const [isOpen, setIsOpen] = useState(false);

  const handleExport = (format: ExportFormat) => {
    onExport(format);
    setIsOpen(false);
  };

  return (
    <div className="relative">
      <Button
        variant="outline"
        disabled={disabled}
        onClick={() => setIsOpen(!isOpen)}
        className="gap-2"
      >
        <Download className="h-4 w-4" />
        {label}
        <ChevronDown className={`h-4 w-4 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </Button>

      {isOpen && (
        <>
          {/* Backdrop to close menu */}
          <div
            className="fixed inset-0 z-40"
            onClick={() => setIsOpen(false)}
          />

          {/* Dropdown menu */}
          <div className="absolute right-0 mt-2 w-48 bg-popover border rounded-md shadow-lg z-50">
            <div className="p-1">
              <button
                onClick={() => handleExport('csv')}
                className="flex items-center gap-2 w-full px-3 py-2 text-sm rounded-sm hover:bg-muted transition-colors text-left"
              >
                <FileSpreadsheet className="h-4 w-4 text-green-600" />
                <div>
                  <div className="font-medium">Export as CSV</div>
                  <div className="text-xs text-muted-foreground">Spreadsheet format</div>
                </div>
              </button>
              <button
                onClick={() => handleExport('json')}
                className="flex items-center gap-2 w-full px-3 py-2 text-sm rounded-sm hover:bg-muted transition-colors text-left"
              >
                <FileJson className="h-4 w-4 text-blue-600" />
                <div>
                  <div className="font-medium">Export as JSON</div>
                  <div className="text-xs text-muted-foreground">Structured data format</div>
                </div>
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
