import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { LandingLayout } from '@web/components/landing/LandingLayout';

vi.mock('next/head', () => ({
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock('next/link', () => ({
  default: ({
    href,
    children,
    ...rest
  }: {
    href: string;
    children: React.ReactNode;
  }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

describe('LandingLayout research handoff', () => {
  it('routes all Researchers navigation links to the deep research console', () => {
    render(
      <LandingLayout
        title="Researchers"
        description="Research workspace"
        segment="researchers"
      >
        <div>Landing body</div>
      </LandingLayout>
    );

    const researcherLinks = screen.getAllByRole('link', { name: 'Researchers' });

    expect(researcherLinks).toHaveLength(2);
    expect(researcherLinks.map((link) => link.getAttribute('href'))).toEqual([
      '/research',
      '/research',
    ]);
  });
});
