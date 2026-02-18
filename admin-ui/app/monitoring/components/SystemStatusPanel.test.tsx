/* @vitest-environment jsdom */
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import SystemStatusPanel from './SystemStatusPanel';

const healthyStatus = [
  {
    key: 'api' as const,
    label: 'API',
    status: 'healthy' as const,
    detail: 'Healthy',
    lastCheckedAt: '2026-02-18T12:00:00.000Z',
    responseTimeMs: 42,
  },
];

describe('SystemStatusPanel', () => {
  it('uses assertive live announcements when status severity escalates', () => {
    const { rerender } = render(<SystemStatusPanel systemStatus={healthyStatus} />);
    const liveRegion = screen.getByTestId('system-status-live-region');
    expect(liveRegion.getAttribute('aria-live')).toBe('polite');

    rerender(
      <SystemStatusPanel
        systemStatus={[
          {
            ...healthyStatus[0],
            status: 'warning',
            detail: 'Latency degraded',
          },
        ]}
      />
    );

    expect(screen.getByTestId('system-status-live-region').getAttribute('aria-live')).toBe('assertive');
  });
});
