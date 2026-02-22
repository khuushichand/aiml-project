import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { AlertTriangle, Trash2 } from 'lucide-react';
import {
  ALERT_RULE_DURATION_OPTIONS,
  ALERT_RULE_METRIC_OPTIONS,
  ALERT_RULE_OPERATOR_OPTIONS,
  ALERT_SEVERITY_OPTIONS,
} from '@/lib/monitoring-alerts';
import type {
  AlertRule,
  AlertRuleDraft,
  AlertRuleValidationErrors,
} from '../types';

type AlertRulesPanelProps = {
  rules: AlertRule[];
  draft: AlertRuleDraft;
  errors: AlertRuleValidationErrors;
  saving: boolean;
  onDraftChange: (draft: AlertRuleDraft) => void;
  onCreateRule: () => void;
  onDeleteRule: (rule: AlertRule) => void;
};

const formatDuration = (minutes: number): string => {
  if (minutes < 60) {
    return `${minutes}m`;
  }
  if (minutes % 60 === 0) {
    return `${minutes / 60}h`;
  }
  const hours = Math.floor(minutes / 60);
  return `${hours}h ${minutes % 60}m`;
};

const formatMetric = (metric: string): string =>
  ALERT_RULE_METRIC_OPTIONS.find((option) => option.value === metric)?.label ?? metric;

export default function AlertRulesPanel({
  rules,
  draft,
  errors,
  saving,
  onDraftChange,
  onCreateRule,
  onDeleteRule,
}: AlertRulesPanelProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <AlertTriangle className="h-5 w-5" />
          Alert Rules
        </CardTitle>
        <CardDescription>
          Define threshold-based rule conditions for warning and critical alerts.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-3 md:grid-cols-5">
          <div className="space-y-1">
            <Label htmlFor="alert-rule-metric">Metric</Label>
            <Select
              id="alert-rule-metric"
              value={draft.metric}
              onChange={(event) => {
                onDraftChange({ ...draft, metric: event.target.value as AlertRuleDraft['metric'] });
              }}
              aria-invalid={errors.metric ? 'true' : undefined}
            >
              {ALERT_RULE_METRIC_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
            {errors.metric ? <p className="text-xs text-destructive">{errors.metric}</p> : null}
          </div>

          <div className="space-y-1">
            <Label htmlFor="alert-rule-operator">Operator</Label>
            <Select
              id="alert-rule-operator"
              value={draft.operator}
              onChange={(event) => {
                onDraftChange({ ...draft, operator: event.target.value as AlertRuleDraft['operator'] });
              }}
              aria-invalid={errors.operator ? 'true' : undefined}
            >
              {ALERT_RULE_OPERATOR_OPTIONS.map((operator) => (
                <option key={operator} value={operator}>
                  {operator}
                </option>
              ))}
            </Select>
            {errors.operator ? <p className="text-xs text-destructive">{errors.operator}</p> : null}
          </div>

          <div className="space-y-1">
            <Label htmlFor="alert-rule-threshold">Threshold</Label>
            <Input
              id="alert-rule-threshold"
              value={draft.threshold}
              onChange={(event) => {
                onDraftChange({ ...draft, threshold: event.target.value });
              }}
              inputMode="decimal"
              aria-invalid={errors.threshold ? 'true' : undefined}
            />
            {errors.threshold ? <p className="text-xs text-destructive">{errors.threshold}</p> : null}
          </div>

          <div className="space-y-1">
            <Label htmlFor="alert-rule-duration">Duration</Label>
            <Select
              id="alert-rule-duration"
              value={draft.durationMinutes}
              onChange={(event) => {
                onDraftChange({ ...draft, durationMinutes: event.target.value });
              }}
              aria-invalid={errors.durationMinutes ? 'true' : undefined}
            >
              {ALERT_RULE_DURATION_OPTIONS.map((option) => (
                <option key={option.value} value={String(option.value)}>
                  {option.label}
                </option>
              ))}
            </Select>
            {errors.durationMinutes ? (
              <p className="text-xs text-destructive">{errors.durationMinutes}</p>
            ) : null}
          </div>

          <div className="space-y-1">
            <Label htmlFor="alert-rule-severity">Severity</Label>
            <Select
              id="alert-rule-severity"
              value={draft.severity}
              onChange={(event) => {
                onDraftChange({ ...draft, severity: event.target.value as AlertRuleDraft['severity'] });
              }}
              aria-invalid={errors.severity ? 'true' : undefined}
            >
              {ALERT_SEVERITY_OPTIONS.map((severity) => (
                <option key={severity} value={severity}>
                  {severity}
                </option>
              ))}
            </Select>
            {errors.severity ? <p className="text-xs text-destructive">{errors.severity}</p> : null}
          </div>
        </div>

        <div className="flex justify-end">
          <Button
            type="button"
            onClick={onCreateRule}
            loading={saving}
            loadingText="Saving..."
            data-testid="alert-rule-create"
          >
            Add Rule
          </Button>
        </div>

        <div className="space-y-2">
          {rules.length === 0 ? (
            <div className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
              No alert rules configured yet.
            </div>
          ) : (
            rules.map((rule) => (
              <div key={rule.id} className="flex items-center justify-between rounded-md border p-3">
                <div className="flex flex-wrap items-center gap-2 text-sm">
                  <span className="font-medium">{formatMetric(rule.metric)}</span>
                  <Badge variant="outline">{rule.operator}</Badge>
                  <span>{rule.threshold}</span>
                  <span className="text-muted-foreground">for {formatDuration(rule.durationMinutes)}</span>
                  <Badge
                    variant={rule.severity === 'critical' || rule.severity === 'error' ? 'destructive' : 'secondary'}
                    className="capitalize"
                  >
                    {rule.severity}
                  </Badge>
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => onDeleteRule(rule)}
                  aria-label={`Delete rule ${rule.id}`}
                >
                  <Trash2 className="h-4 w-4 text-destructive" />
                </Button>
              </div>
            ))
          )}
        </div>
      </CardContent>
    </Card>
  );
}
