import { Download } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import type { Invoice } from '@/types';

interface InvoiceTableProps {
  invoices: Invoice[];
}

function formatCents(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
}

const statusVariant: Record<string, 'default' | 'secondary' | 'destructive' | 'outline'> = {
  paid: 'default',
  open: 'outline',
  void: 'secondary',
  draft: 'secondary',
  uncollectible: 'destructive',
};

export function InvoiceTable({ invoices }: InvoiceTableProps) {
  if (invoices.length === 0) {
    return <p className="text-sm text-muted-foreground py-4 text-center">No invoices yet.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left text-muted-foreground">
            <th className="py-2 pr-4">Date</th>
            <th className="py-2 pr-4">Period</th>
            <th className="py-2 pr-4">Amount</th>
            <th className="py-2 pr-4">Status</th>
            <th className="py-2" />
          </tr>
        </thead>
        <tbody>
          {invoices.map((inv) => (
            <tr key={inv.id} className="border-b">
              <td className="py-2 pr-4">{formatDate(inv.created_at)}</td>
              <td className="py-2 pr-4">
                {formatDate(inv.period_start)} — {formatDate(inv.period_end)}
              </td>
              <td className="py-2 pr-4 font-medium">{formatCents(inv.amount_cents)}</td>
              <td className="py-2 pr-4">
                <Badge variant={statusVariant[inv.status] ?? 'outline'}>{inv.status}</Badge>
              </td>
              <td className="py-2">
                {inv.invoice_pdf && (
                  <a
                    href={inv.invoice_pdf}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-muted-foreground hover:text-foreground"
                  >
                    <Download className="h-3 w-3" /> PDF
                  </a>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
