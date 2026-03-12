import { render, screen, cleanup } from '@testing-library/react';
import { afterEach, describe, it, expect } from 'vitest';
import { UsageMeter } from '../UsageMeter';

afterEach(cleanup);

describe('UsageMeter', () => {
  it('renders used and included token counts', () => {
    render(<UsageMeter used={500_000} included={1_000_000} overageCostCents={0} />);
    expect(screen.getByText(/500,000/)).toBeInTheDocument();
    expect(screen.getByText(/1,000,000/)).toBeInTheDocument();
  });

  it('shows green bar when under 80% usage', () => {
    const { container } = render(<UsageMeter used={400_000} included={1_000_000} overageCostCents={0} />);
    const bar = container.querySelector('[data-testid="usage-bar"]');
    expect(bar?.className).toContain('bg-green');
  });

  it('shows yellow bar when between 80-100% usage', () => {
    const { container } = render(<UsageMeter used={850_000} included={1_000_000} overageCostCents={0} />);
    const bar = container.querySelector('[data-testid="usage-bar"]');
    expect(bar?.className).toContain('bg-yellow');
  });

  it('shows red bar and overage cost when over 100%', () => {
    render(<UsageMeter used={1_200_000} included={1_000_000} overageCostCents={2400} />);
    const bar = screen.getByTestId('usage-bar');
    expect(bar.className).toContain('bg-red');
    expect(screen.getByText(/\$24\.00/)).toBeInTheDocument();
  });

  it('handles zero included gracefully', () => {
    render(<UsageMeter used={100} included={0} overageCostCents={0} />);
    expect(screen.getByText(/100 \/ 0 tokens/)).toBeInTheDocument();
    expect(screen.getByText(/100\.0% used/)).toBeInTheDocument();
  });
});
