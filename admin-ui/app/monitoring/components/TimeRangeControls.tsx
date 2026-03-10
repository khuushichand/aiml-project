import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import type { MonitoringTimeRangeOption } from '@/lib/monitoring-metrics';

type TimeRangeOption = {
  value: MonitoringTimeRangeOption;
  label: string;
};

type TimeRangeControlsProps = {
  options: TimeRangeOption[];
  timeRange: MonitoringTimeRangeOption;
  customRangeStart: string;
  customRangeEnd: string;
  rangeValidationError: string;
  onSelectTimeRange: (value: MonitoringTimeRangeOption) => Promise<boolean> | boolean | void;
  onCustomRangeStartChange: (value: string) => void;
  onCustomRangeEndChange: (value: string) => void;
  onApplyCustomRange: () => Promise<boolean> | boolean | void;
};

export default function TimeRangeControls({
  options,
  timeRange,
  customRangeStart,
  customRangeEnd,
  rangeValidationError,
  onSelectTimeRange,
  onCustomRangeStartChange,
  onCustomRangeEndChange,
  onApplyCustomRange,
}: TimeRangeControlsProps) {
  return (
    <div className="mb-4 rounded-lg border border-border/80 bg-muted/10 p-4">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium">Time Range</span>
        {options.map((option) => (
          <Button
            key={option.value}
            type="button"
            size="sm"
            variant={timeRange === option.value ? 'secondary' : 'outline'}
            onClick={() => {
              void onSelectTimeRange(option.value);
            }}
            data-testid={`monitoring-time-range-${option.value}`}
          >
            {option.label}
          </Button>
        ))}
      </div>
      {timeRange === 'custom' && (
        <div className="grid gap-3 md:grid-cols-[1fr_1fr_auto] md:items-end">
          <div className="space-y-1">
            <Label htmlFor="customRangeStart">Custom Start</Label>
            <Input
              id="customRangeStart"
              type="datetime-local"
              value={customRangeStart}
              onChange={(event) => {
                onCustomRangeStartChange(event.target.value);
              }}
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="customRangeEnd">Custom End</Label>
            <Input
              id="customRangeEnd"
              type="datetime-local"
              value={customRangeEnd}
              onChange={(event) => {
                onCustomRangeEndChange(event.target.value);
              }}
            />
          </div>
          <Button
            type="button"
            onClick={() => {
              void onApplyCustomRange();
            }}
            data-testid="monitoring-time-range-apply-custom"
          >
            Apply
          </Button>
        </div>
      )}
      {rangeValidationError && (
        <p className="mt-2 text-sm text-destructive">{rangeValidationError}</p>
      )}
    </div>
  );
}
