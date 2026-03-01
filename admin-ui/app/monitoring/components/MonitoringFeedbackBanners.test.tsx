/* @vitest-environment jsdom */
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import MonitoringFeedbackBanners from './MonitoringFeedbackBanners';

describe('MonitoringFeedbackBanners', () => {
  afterEach(() => {
    cleanup();
  });

  it('renders error, success, and active alert banners when present', () => {
    render(
      <MonitoringFeedbackBanners
        error="Failed to load monitoring data"
        success="Watchlist created"
        activeAlertsCount={2}
      />
    );

    expect(screen.getByText('Failed to load monitoring data')).toBeInTheDocument();
    expect(screen.getByText('Watchlist created')).toBeInTheDocument();
    expect(screen.getByText('2 active alerts require attention')).toBeInTheDocument();
    expect(
      screen.getByTestId('monitoring-alert-count-live').textContent
    ).toContain('2 active alerts currently require attention.');
  });

  it('keeps the live region while omitting optional banners', () => {
    render(
      <MonitoringFeedbackBanners
        error=""
        success=""
        activeAlertsCount={0}
      />
    );

    expect(
      screen.getByTestId('monitoring-alert-count-live').textContent
    ).toContain('0 active alerts currently require attention.');
    expect(screen.queryByText('Failed to load monitoring data')).not.toBeInTheDocument();
    expect(screen.queryByText('Watchlist created')).not.toBeInTheDocument();
    expect(screen.queryByText(/require attention$/)).not.toBeInTheDocument();
  });
});
