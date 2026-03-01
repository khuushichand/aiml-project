/* @vitest-environment jsdom */
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { MonitoringTimeRangeOption } from '@/lib/monitoring-metrics';
import TimeRangeControls from './TimeRangeControls';

const options: Array<{ value: MonitoringTimeRangeOption; label: string }> = [
  { value: '1h', label: '1h' },
  { value: '24h', label: '24h' },
  { value: 'custom', label: 'Custom' },
];

describe('TimeRangeControls', () => {
  it('renders options and forwards time range selection', () => {
    const onSelectTimeRange = vi.fn();
    render(
      <TimeRangeControls
        options={options}
        timeRange="24h"
        customRangeStart=""
        customRangeEnd=""
        rangeValidationError=""
        onSelectTimeRange={onSelectTimeRange}
        onCustomRangeStartChange={vi.fn()}
        onCustomRangeEndChange={vi.fn()}
        onApplyCustomRange={vi.fn()}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: '1h' }));
    expect(onSelectTimeRange).toHaveBeenCalledWith('1h');
  });

  it('shows custom controls and forwards custom range interactions', () => {
    const onCustomRangeStartChange = vi.fn();
    const onCustomRangeEndChange = vi.fn();
    const onApplyCustomRange = vi.fn();

    render(
      <TimeRangeControls
        options={options}
        timeRange="custom"
        customRangeStart="2026-02-28T10:00"
        customRangeEnd="2026-02-28T11:00"
        rangeValidationError="Start must be before end"
        onSelectTimeRange={vi.fn()}
        onCustomRangeStartChange={onCustomRangeStartChange}
        onCustomRangeEndChange={onCustomRangeEndChange}
        onApplyCustomRange={onApplyCustomRange}
      />
    );

    fireEvent.change(screen.getByLabelText('Custom Start'), {
      target: { value: '2026-02-28T09:00' },
    });
    fireEvent.change(screen.getByLabelText('Custom End'), {
      target: { value: '2026-02-28T12:00' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }));

    expect(onCustomRangeStartChange).toHaveBeenCalledWith('2026-02-28T09:00');
    expect(onCustomRangeEndChange).toHaveBeenCalledWith('2026-02-28T12:00');
    expect(onApplyCustomRange).toHaveBeenCalledTimes(1);
    expect(screen.getByText('Start must be before end')).toBeInTheDocument();
  });
});
