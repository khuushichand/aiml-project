import { useEffect, useRef, useState } from 'react';
import {
  buildAlertRuleFromDraft,
  DEFAULT_ALERT_RULE_DRAFT,
  readStoredAlertRules,
  validateAlertRuleDraft,
  writeStoredAlertRules,
} from '@/lib/monitoring-alerts';
import type {
  AlertRule,
  AlertRuleDraft,
  AlertRuleValidationErrors,
} from './types';

type UseAlertRulesArgs = {
  setSuccess: (message: string) => void;
};

export const useAlertRules = ({
  setSuccess,
}: UseAlertRulesArgs) => {
  const [alertRules, setAlertRules] = useState<AlertRule[]>([]);
  const [alertRuleDraft, setAlertRuleDraft] = useState<AlertRuleDraft>(DEFAULT_ALERT_RULE_DRAFT);
  const [alertRuleValidationErrors, setAlertRuleValidationErrors] = useState<AlertRuleValidationErrors>({});
  const [alertRulesSaving, setAlertRulesSaving] = useState(false);
  const alertRulesHydratedRef = useRef(false);

  useEffect(() => {
    setAlertRules(readStoredAlertRules());
    alertRulesHydratedRef.current = true;
  }, []);

  useEffect(() => {
    if (!alertRulesHydratedRef.current) return;
    writeStoredAlertRules(alertRules);
  }, [alertRules]);

  const handleAlertRuleDraftChange = (draft: AlertRuleDraft) => {
    setAlertRuleDraft(draft);
    setAlertRuleValidationErrors({});
  };

  const handleCreateAlertRule = () => {
    const validation = validateAlertRuleDraft(alertRuleDraft);
    if (!validation.valid) {
      setAlertRuleValidationErrors(validation.errors);
      return;
    }

    setAlertRulesSaving(true);
    try {
      const newRule = buildAlertRuleFromDraft(alertRuleDraft);
      setAlertRules((prev) => [newRule, ...prev]);
      setAlertRuleValidationErrors({});
      setAlertRuleDraft(DEFAULT_ALERT_RULE_DRAFT);
      setSuccess('Alert rule added');
    } finally {
      setAlertRulesSaving(false);
    }
  };

  const handleDeleteAlertRule = (rule: AlertRule) => {
    setAlertRules((prev) => prev.filter((item) => item.id !== rule.id));
    setSuccess('Alert rule deleted');
  };

  return {
    alertRules,
    alertRuleDraft,
    alertRuleValidationErrors,
    alertRulesSaving,
    handleAlertRuleDraftChange,
    handleCreateAlertRule,
    handleDeleteAlertRule,
  };
};
