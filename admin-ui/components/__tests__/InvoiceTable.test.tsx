import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { InvoiceTable } from '../InvoiceTable';
import type { Invoice } from '@/types';

const invoices: Invoice[] = [
  {
    id: '1',
    stripe_invoice_id: 'inv_abc',
    amount_cents: 4900,
    currency: 'usd',
    status: 'paid',
    invoice_pdf: 'https://stripe.com/invoice.pdf',
    period_start: '2026-02-01T00:00:00Z',
    period_end: '2026-03-01T00:00:00Z',
    created_at: '2026-03-01T00:00:00Z',
  },
  {
    id: '2',
    stripe_invoice_id: 'inv_def',
    amount_cents: 7500,
    currency: 'usd',
    status: 'open',
    period_start: '2026-03-01T00:00:00Z',
    period_end: '2026-04-01T00:00:00Z',
    created_at: '2026-04-01T00:00:00Z',
  },
];

describe('InvoiceTable', () => {
  it('renders invoice rows', () => {
    render(<InvoiceTable invoices={invoices} />);
    expect(screen.getByText('$49.00')).toBeInTheDocument();
    expect(screen.getByText('$75.00')).toBeInTheDocument();
  });

  it('renders status badges', () => {
    render(<InvoiceTable invoices={invoices} />);
    const paidBadges = screen.getAllByText('paid');
    expect(paidBadges.length).toBeGreaterThanOrEqual(1);
    const openBadges = screen.getAllByText('open');
    expect(openBadges.length).toBeGreaterThanOrEqual(1);
  });

  it('renders PDF download link when available', () => {
    render(<InvoiceTable invoices={invoices} />);
    const links = screen.getAllByRole('link');
    expect(links.some((link) => link.getAttribute('href') === 'https://stripe.com/invoice.pdf')).toBe(true);
  });

  it('renders empty state when no invoices', () => {
    render(<InvoiceTable invoices={[]} />);
    expect(screen.getByText(/no invoices/i)).toBeInTheDocument();
  });
});
