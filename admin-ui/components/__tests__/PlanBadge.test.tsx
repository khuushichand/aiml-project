import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { PlanBadge } from '../PlanBadge';

describe('PlanBadge', () => {
  it('renders the plan tier label', () => {
    render(<PlanBadge tier="pro" />);
    expect(screen.getByText('Pro')).toBeInTheDocument();
  });

  it('renders free tier', () => {
    const { container } = render(<PlanBadge tier="free" />);
    const badge = container.firstChild as HTMLElement;
    expect(badge.textContent).toBe('Free');
  });

  it('renders enterprise tier', () => {
    render(<PlanBadge tier="enterprise" />);
    expect(screen.getByText('Enterprise')).toBeInTheDocument();
  });

  it('applies additional className', () => {
    const { container } = render(<PlanBadge tier="pro" className="ml-2" />);
    const badge = container.firstChild as HTMLElement;
    expect(badge.className).toContain('ml-2');
  });
});
