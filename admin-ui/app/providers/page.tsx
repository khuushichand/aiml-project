'use client';

import { useCallback, useEffect, useState } from 'react';
import { PermissionGuard } from '@/components/PermissionGuard';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useConfirm } from '@/components/ui/confirm-dialog';
import { useToast } from '@/components/ui/toast';
import { Checkbox } from '@/components/ui/checkbox';
import { Cpu, RefreshCw, CheckCircle, XCircle, Key, ExternalLink, Plus, Trash2, Search, Building2, User, Settings, Activity } from 'lucide-react';
import { api } from '@/lib/api-client';
import { LLMProvider, LLMProviderOverride, User as UserType, Organization } from '@/types';

interface ByokKey {
  id?: string;
  provider: string;
  key_hint?: string;
  created_at?: string;
}

interface ProviderConfig {
  enabled?: boolean;
  models?: string[];
  default_model?: string;
  override?: LLMProviderOverride;
  [key: string]: unknown;
}

interface OverrideDialogState {
  isOpen: boolean;
  provider: LLMProvider | null;
  override: LLMProviderOverride | null;
  enabled: boolean;
  allowedModels: string;
  defaultModel: string;
  baseUrl: string;
  apiKey: string;
  clearApiKey: boolean;
  isSaving: boolean;
  isDeleting: boolean;
}

interface ByokState {
  users: UserType[];
  organizations: Organization[];
  selectedUser: UserType | null;
  selectedOrg: Organization | null;
  userKeys: ByokKey[];
  orgKeys: ByokKey[];
  isLoading: boolean;
  userSearch: string;
  userLimit: number;
}

interface AddByokDialogState {
  isOpen: boolean;
  mode: 'user' | 'org';
  provider: string;
  customProviderName: string;
  apiKey: string;
  isAdding: boolean;
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null;

const getStringValue = (value: unknown): string =>
  typeof value === 'string' ? value : '';

interface ByokKeysTableProps {
  keys: ByokKey[];
  onDelete: (provider: string) => void;
  formatProviderName: (name: string) => string;
  deletingProvider?: string | null;
}

function ByokKeysTable({ keys, onDelete, formatProviderName, deletingProvider }: ByokKeysTableProps) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Provider</TableHead>
          <TableHead>Key Hint</TableHead>
          <TableHead>Created</TableHead>
          <TableHead className="text-right">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {keys.map((key) => {
          const isDeleting = deletingProvider === key.provider;
          return (
          <TableRow key={key.provider}>
            <TableCell>
              <div className="font-medium">{formatProviderName(key.provider)}</div>
            </TableCell>
            <TableCell>
              <code className="text-xs bg-muted px-2 py-1 rounded">
                {key.key_hint || '****...****'}
              </code>
            </TableCell>
            <TableCell className="text-sm text-muted-foreground">
              {key.created_at
                ? new Date(key.created_at).toLocaleDateString()
                : '-'}
            </TableCell>
            <TableCell className="text-right">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onDelete(key.provider)}
                disabled={isDeleting}
              >
                <Trash2 className="h-4 w-4 text-red-500" />
              </Button>
            </TableCell>
          </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}

export default function ProvidersPage() {
  const confirm = useConfirm();
  const { success: toastSuccess, error: toastError } = useToast();
  const [providers, setProviders] = useState<LLMProvider[]>([]);
  const [providerOverrides, setProviderOverrides] = useState<Record<string, LLMProviderOverride>>({});
  const [loading, setLoading] = useState(true);
  const [overrideDialog, setOverrideDialog] = useState<OverrideDialogState>({
    isOpen: false,
    provider: null,
    override: null,
    enabled: true,
    allowedModels: '',
    defaultModel: '',
    baseUrl: '',
    apiKey: '',
    clearApiKey: false,
    isSaving: false,
    isDeleting: false,
  });
  const [testingProvider, setTestingProvider] = useState<string | null>(null);
  const [deletingUserByokProvider, setDeletingUserByokProvider] = useState<string | null>(null);
  const [deletingOrgByokProvider, setDeletingOrgByokProvider] = useState<string | null>(null);

  // BYOK management state
  const [byokState, setByokState] = useState<ByokState>({
    users: [],
    organizations: [],
    selectedUser: null,
    selectedOrg: null,
    userKeys: [],
    orgKeys: [],
    isLoading: false,
    userSearch: '',
    userLimit: 20,
  });

  // Add BYOK dialog
  const [addByokDialog, setAddByokDialog] = useState<AddByokDialogState>({
    isOpen: false,
    mode: 'user',
    provider: '',
    customProviderName: '',
    apiKey: '',
    isAdding: false,
  });

  const updateOverrideDialog = (updates: Partial<OverrideDialogState>) => {
    setOverrideDialog((prev) => ({ ...prev, ...updates }));
  };

  const updateByokState = (updates: Partial<ByokState>) => {
    setByokState((prev) => ({ ...prev, ...updates }));
  };

  const updateAddByokDialog = (updates: Partial<AddByokDialogState>) => {
    setAddByokDialog((prev) => ({ ...prev, ...updates }));
  };

  const loadData = useCallback(async () => {
    try {
      setLoading(true);

      const [providersData, usersData, orgsData, overridesData] = await Promise.allSettled([
        api.getLLMProviders(),
        api.getUsers(),
        api.getOrganizations(),
        api.getLLMProviderOverrides(),
      ]);

      if (providersData.status === 'fulfilled') {
        let providersArray: LLMProvider[] = [];
        const payload = providersData.value;
        if (Array.isArray(payload)) {
          providersArray = payload;
        } else if (payload && typeof payload === 'object' && Array.isArray((payload as { providers?: unknown }).providers)) {
          providersArray = (payload as { providers: LLMProvider[] }).providers;
        } else if (payload && typeof payload === 'object') {
          providersArray = Object.entries(payload as Record<string, ProviderConfig>).map(([name, value]) => ({
            ...value,
            name,
            enabled: value.enabled ?? true,
            models: value.models || [],
          }));
        }
        setProviders(providersArray);
      }

      if (usersData.status === 'fulfilled') {
        const users = Array.isArray(usersData.value) ? usersData.value : [];
        setByokState((prev) => ({ ...prev, users }));
      }

      if (orgsData.status === 'fulfilled') {
        const organizations = Array.isArray(orgsData.value) ? orgsData.value : [];
        setByokState((prev) => ({ ...prev, organizations }));
      }

      if (overridesData.status === 'fulfilled') {
        const items = (overridesData.value && typeof overridesData.value === 'object' && Array.isArray((overridesData.value as { items?: unknown }).items))
          ? (overridesData.value as { items: LLMProviderOverride[] }).items
          : [];
        const map: Record<string, LLMProviderOverride> = {};
        items.forEach((item) => {
          if (item?.provider) {
            map[item.provider.toLowerCase()] = item;
          }
        });
        setProviderOverrides(map);
      }
    } catch (err: unknown) {
      console.error('Failed to load data:', err);
      toastError('Failed to load providers', err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      setLoading(false);
    }
  }, [toastError]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const loadUserByokKeys = async (user: UserType) => {
    updateByokState({ selectedUser: user, isLoading: true });
    try {
      const keys = await api.getUserByokKeys(user.id.toString());
      updateByokState({ userKeys: Array.isArray(keys) ? keys : [] });
    } catch (err: unknown) {
      console.error('Failed to load user BYOK keys:', err);
      updateByokState({ userKeys: [] });
      toastError('Failed to load user keys', err instanceof Error ? err.message : 'Unable to load BYOK keys');
    } finally {
      updateByokState({ isLoading: false });
    }
  };

  const loadOrgByokKeys = async (org: Organization) => {
    updateByokState({ selectedOrg: org, isLoading: true });
    try {
      const keys = await api.getOrgByokKeys(org.id.toString());
      updateByokState({ orgKeys: Array.isArray(keys) ? keys : [] });
    } catch (err: unknown) {
      console.error('Failed to load org BYOK keys:', err);
      updateByokState({ orgKeys: [] });
      toastError('Failed to load org keys', err instanceof Error ? err.message : 'Unable to load BYOK keys');
    } finally {
      updateByokState({ isLoading: false });
    }
  };

  const handleAddByok = async () => {
    const providerName = addByokDialog.provider === 'other'
      ? addByokDialog.customProviderName.trim()
      : addByokDialog.provider.trim();
    if (!canSubmitByok) {
      toastError('Missing fields', byokValidationError || 'Provider and API key are required');
      return;
    }

    updateAddByokDialog({ isAdding: true });
    try {
      const data = {
        provider: providerName.trim().toLowerCase(),
        api_key: addByokDialog.apiKey.trim(),
      };

      if (addByokDialog.mode === 'user' && byokState.selectedUser) {
        await api.createUserByokKey(byokState.selectedUser.id.toString(), data);
        await loadUserByokKeys(byokState.selectedUser);
        toastSuccess('BYOK key added', `Added for ${byokState.selectedUser.email}`);
      } else if (addByokDialog.mode === 'org' && byokState.selectedOrg) {
        await api.createOrgByokKey(byokState.selectedOrg.id.toString(), data);
        await loadOrgByokKeys(byokState.selectedOrg);
        toastSuccess('BYOK key added', `Added for ${byokState.selectedOrg.name}`);
      }

      updateAddByokDialog({
        isOpen: false,
        provider: '',
        customProviderName: '',
        apiKey: '',
      });
    } catch (err: unknown) {
      console.error('Failed to add BYOK key:', err);
      toastError('Failed to add BYOK key', err instanceof Error ? err.message : 'Try again.');
    } finally {
      updateAddByokDialog({ isAdding: false });
    }
  };

  const handleDeleteUserByok = async (provider: string) => {
    if (!byokState.selectedUser) return;
    if (deletingUserByokProvider === provider) return;

    const confirmed = await confirm({
      title: 'Delete API Key',
      message: `Delete ${provider} key for ${byokState.selectedUser.email}?`,
      confirmText: 'Delete',
      variant: 'danger',
      icon: 'key',
    });
    if (!confirmed) return;

    try {
      setDeletingUserByokProvider(provider);
      await api.deleteUserByokKey(byokState.selectedUser.id.toString(), provider);
      await loadUserByokKeys(byokState.selectedUser);
      toastSuccess('BYOK key deleted', `Removed ${provider} for ${byokState.selectedUser.email}`);
    } catch (err: unknown) {
      console.error('Failed to delete BYOK key:', err);
      toastError('Failed to delete BYOK key', err instanceof Error ? err.message : 'Try again.');
    } finally {
      setDeletingUserByokProvider((prev) => (prev === provider ? null : prev));
    }
  };

  const handleDeleteOrgByok = async (provider: string) => {
    if (!byokState.selectedOrg) return;
    if (deletingOrgByokProvider === provider) return;

    const confirmed = await confirm({
      title: 'Delete API Key',
      message: `Delete ${provider} key for ${byokState.selectedOrg.name}?`,
      confirmText: 'Delete',
      variant: 'danger',
      icon: 'key',
    });
    if (!confirmed) return;

    try {
      setDeletingOrgByokProvider(provider);
      await api.deleteOrgByokKey(byokState.selectedOrg.id.toString(), provider);
      await loadOrgByokKeys(byokState.selectedOrg);
      toastSuccess('BYOK key deleted', `Removed ${provider} for ${byokState.selectedOrg.name}`);
    } catch (err: unknown) {
      console.error('Failed to delete BYOK key:', err);
      toastError('Failed to delete BYOK key', err instanceof Error ? err.message : 'Try again.');
    } finally {
      setDeletingOrgByokProvider((prev) => (prev === provider ? null : prev));
    }
  };

  const openAddByokDialog = (mode: 'user' | 'org') => {
    updateAddByokDialog({
      mode,
      provider: '',
      customProviderName: '',
      apiKey: '',
      isAdding: false,
      isOpen: true,
    });
  };

  const getProviderDocs = (name: string): string | null => {
    const docs: Record<string, string> = {
      openai: 'https://platform.openai.com/docs',
      anthropic: 'https://docs.anthropic.com',
      google: 'https://ai.google.dev/docs',
      cohere: 'https://docs.cohere.com',
      groq: 'https://console.groq.com/docs',
      mistral: 'https://docs.mistral.ai',
      deepseek: 'https://platform.deepseek.com/docs',
      ollama: 'https://ollama.com/docs',
      openrouter: 'https://openrouter.ai/docs',
    };
    return docs[name.toLowerCase()] || null;
  };

  const formatProviderName = (name: string): string => {
    const names: Record<string, string> = {
      openai: 'OpenAI',
      anthropic: 'Anthropic',
      google: 'Google AI',
      cohere: 'Cohere',
      groq: 'Groq',
      mistral: 'Mistral AI',
      deepseek: 'DeepSeek',
      ollama: 'Ollama',
      openrouter: 'OpenRouter',
      huggingface: 'HuggingFace',
      kobold: 'KoboldCpp',
      llamacpp: 'Llama.cpp',
      tabbyapi: 'TabbyAPI',
      vllm: 'vLLM',
      aphrodite: 'Aphrodite',
      custom: 'Custom OpenAI',
    };
    return names[name.toLowerCase()] || name;
  };

  const getOverrideForProvider = (provider: LLMProvider): LLMProviderOverride | undefined => {
    const key = provider.name.toLowerCase();
    return providerOverrides[key] || provider.override;
  };

  const openOverrideDialog = (provider: LLMProvider) => {
    const override = getOverrideForProvider(provider);
    setOverrideDialog({
      isOpen: true,
      provider,
      override: override || null,
      enabled: override?.is_enabled ?? provider.enabled ?? true,
      allowedModels: override?.allowed_models?.join(', ') ?? '',
      defaultModel: getStringValue(override?.config?.default_model),
      baseUrl: getStringValue(override?.credential_fields?.base_url),
      apiKey: '',
      clearApiKey: false,
      isSaving: false,
    });
  };

  const handleSaveOverride = async () => {
    if (!overrideDialog.provider) return;
    updateOverrideDialog({ isSaving: true });

    const allowedModels = overrideDialog.allowedModels
      .split(',')
      .map((model) => model.trim())
      .filter(Boolean);
    const defaultModelValue = overrideDialog.defaultModel.trim();
    const overrideConfig = overrideDialog.override?.config;
    const configSource = isRecord(overrideConfig) ? overrideConfig : {};
    const config: Record<string, unknown> = { ...configSource };
    if (defaultModelValue) {
      config.default_model = defaultModelValue;
    } else if ('default_model' in configSource) {
      delete config.default_model;
    }
    const credentialFields: Record<string, unknown> = {};
    const overrideCredentials = overrideDialog.override?.credential_fields;
    const credentialSource = isRecord(overrideCredentials)
      ? overrideCredentials
      : {};
    const existingBaseUrl = getStringValue(credentialSource.base_url);
    const trimmedBaseUrl = overrideDialog.baseUrl.trim();
    if (trimmedBaseUrl) {
      credentialFields.base_url = trimmedBaseUrl;
    }

    const payload: Record<string, unknown> = {
      is_enabled: overrideDialog.enabled,
      allowed_models: allowedModels,
    };

    if (defaultModelValue || 'default_model' in configSource) {
      payload.config = config;
    }

    if (Object.keys(credentialFields).length > 0) {
      payload.credential_fields = credentialFields;
    } else if (existingBaseUrl) {
      payload.credential_fields = {};
    }

    if (overrideDialog.apiKey.trim()) {
      payload.api_key = overrideDialog.apiKey.trim();
    } else if (overrideDialog.clearApiKey) {
      payload.clear_api_key = true;
    }

    try {
      await api.updateLLMProviderOverride(overrideDialog.provider.name, payload);
      toastSuccess(
        'Override updated',
        `Updated ${formatProviderName(overrideDialog.provider.name)} overrides.`
      );
      updateOverrideDialog({ isOpen: false });
      await loadData();
    } catch (err: unknown) {
      console.error('Failed to update provider override:', err);
      toastError('Failed to update override', err instanceof Error ? err.message : 'Try again.');
    } finally {
      updateOverrideDialog({ isSaving: false });
    }
  };

  const handleDeleteOverride = async () => {
    if (!overrideDialog.provider) return;
    if (overrideDialog.isDeleting) return;
    const confirmed = await confirm({
      title: 'Remove Override',
      message: `Remove override for ${formatProviderName(overrideDialog.provider.name)}?`,
      confirmText: 'Remove',
      variant: 'danger',
      icon: 'trash',
    });
    if (!confirmed) return;
    try {
      updateOverrideDialog({ isDeleting: true });
      await api.deleteLLMProviderOverride(overrideDialog.provider.name);
      toastSuccess(
        'Override removed',
        `Removed ${formatProviderName(overrideDialog.provider.name)} override.`
      );
      updateOverrideDialog({ isOpen: false });
      await loadData();
    } catch (err: unknown) {
      console.error('Failed to delete provider override:', err);
      toastError('Failed to remove override', err instanceof Error ? err.message : 'Try again.');
    } finally {
      updateOverrideDialog({ isDeleting: false });
    }
  };

  const handleTestProvider = async (provider: LLMProvider) => {
    const override = getOverrideForProvider(provider);
    setTestingProvider(provider.name);
    try {
      const overrideDefaultModel = getStringValue(override?.config?.default_model);
      const response = await api.testLLMProvider({
        provider: provider.name,
        model: overrideDefaultModel || provider.default_model || undefined,
        use_override: true,
      });
      toastSuccess(
        'Connectivity check OK',
        `${formatProviderName(provider.name)} (${response?.model || 'default'})`
      );
    } catch (err: unknown) {
      console.error('Failed to test provider:', err);
      toastError('Provider test failed', err instanceof Error ? err.message : 'Try again.');
    } finally {
      setTestingProvider(null);
    }
  };

  const filteredUsers = byokState.users.filter(
    (u) =>
      byokState.userSearch === '' ||
      u.email?.toLowerCase().includes(byokState.userSearch.toLowerCase()) ||
      u.username?.toLowerCase().includes(byokState.userSearch.toLowerCase())
  );
  const visibleUsers = filteredUsers.slice(0, byokState.userLimit);

  const enabledProviders = providers.filter((p) => p.enabled);
  const disabledProviders = providers.filter((p) => !p.enabled);

  // Common provider options for BYOK
  const commonProviders = ['openai', 'anthropic', 'google', 'cohere', 'groq', 'mistral', 'deepseek', 'openrouter'];
  const byokValidationError = (() => {
    if (addByokDialog.mode === 'user' && !byokState.selectedUser) {
      return 'Choose a user before adding a BYOK key.';
    }
    if (addByokDialog.mode === 'org' && !byokState.selectedOrg) {
      return 'Choose an organization before adding a BYOK key.';
    }
    if (!addByokDialog.provider) {
      return 'Select a provider.';
    }
    if (addByokDialog.provider === 'other' && !addByokDialog.customProviderName.trim()) {
      return 'Enter a provider name.';
    }
    if (!addByokDialog.apiKey.trim()) {
      return 'API key is required.';
    }
    return '';
  })();
  const canSubmitByok = byokValidationError === '';

  return (
    <PermissionGuard variant="route" requireAuth role="admin">
      <ResponsiveLayout>
          <div className="p-4 lg:p-8">
            <div className="mb-8 flex items-center justify-between">
              <div>
                <h1 className="text-3xl font-bold">LLM Providers</h1>
                <p className="text-muted-foreground">
                  Manage LLM providers and BYOK secrets
                </p>
              </div>
              <Button variant="outline" onClick={loadData} disabled={loading}>
                <RefreshCw className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                Refresh
              </Button>
            </div>

            <Tabs defaultValue="providers" className="space-y-4">
              <TabsList>
                <TabsTrigger value="providers">
                  <Cpu className="mr-2 h-4 w-4" />
                  Providers
                </TabsTrigger>
                <TabsTrigger value="user-byok">
                  <User className="mr-2 h-4 w-4" />
                  User BYOK
                </TabsTrigger>
                <TabsTrigger value="org-byok">
                  <Building2 className="mr-2 h-4 w-4" />
                  Org BYOK
                </TabsTrigger>
              </TabsList>

              {/* Providers Tab */}
              <TabsContent value="providers">
                {/* Info Card */}
                <Card className="mb-6">
                  <CardContent className="pt-6">
                    <div className="flex items-start gap-4">
                      <Cpu className="h-8 w-8 text-primary mt-1" />
                      <div>
                        <h3 className="font-semibold">LLM Provider Configuration</h3>
                        <p className="text-sm text-muted-foreground mt-1">
                          tldw_server supports multiple LLM providers including OpenAI, Anthropic, Google, Cohere,
                          and local inference servers. Provider API keys can be configured in the server&apos;s config.txt
                          or .env file.
                        </p>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Summary Stats */}
                <div className="grid gap-4 md:grid-cols-3 mb-6">
                  <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                      <CardTitle className="text-sm font-medium">Total Providers</CardTitle>
                      <Cpu className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                      <div className="text-2xl font-bold">{providers.length}</div>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                      <CardTitle className="text-sm font-medium">Enabled</CardTitle>
                      <CheckCircle className="h-4 w-4 text-green-500" />
                    </CardHeader>
                    <CardContent>
                      <div className="text-2xl font-bold text-green-600">{enabledProviders.length}</div>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                      <CardTitle className="text-sm font-medium">Disabled</CardTitle>
                      <XCircle className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                      <div className="text-2xl font-bold text-muted-foreground">{disabledProviders.length}</div>
                    </CardContent>
                  </Card>
                </div>

                {/* Providers Table */}
                <Card>
                  <CardHeader>
                    <CardTitle>Configured Providers</CardTitle>
                    <CardDescription>
                      All LLM providers available in the system
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    {loading ? (
                      <div className="text-center text-muted-foreground py-8">Loading...</div>
                    ) : providers.length === 0 ? (
                      <div className="text-center text-muted-foreground py-8">
                        <Cpu className="h-12 w-12 mx-auto mb-2 opacity-50" />
                        <p>No LLM providers configured</p>
                        <p className="text-sm mt-1">Configure providers in config.txt or .env</p>
                      </div>
                    ) : (
                      <Table>
                        <TableHeader>
                          <TableRow>
                          <TableHead>Provider</TableHead>
                          <TableHead>Status</TableHead>
                          <TableHead>Models</TableHead>
                          <TableHead>Override</TableHead>
                          <TableHead className="text-right">Actions</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {providers.map((provider) => {
                            const docsUrl = getProviderDocs(provider.name);
                            const override = getOverrideForProvider(provider);
                            return (
                              <TableRow key={provider.name}>
                                <TableCell>
                                  <div className="flex items-center gap-2">
                                    <div className="font-medium">{formatProviderName(provider.name)}</div>
                                    <code className="text-xs bg-muted px-1 rounded">{provider.name}</code>
                                  </div>
                                </TableCell>
                                <TableCell>
                                  {provider.enabled ? (
                                    <Badge variant="default" className="bg-green-500">
                                      <CheckCircle className="mr-1 h-3 w-3" />
                                      Enabled
                                    </Badge>
                                  ) : (
                                    <Badge variant="secondary">
                                      <XCircle className="mr-1 h-3 w-3" />
                                      Disabled
                                    </Badge>
                                  )}
                                </TableCell>
                                <TableCell>
                                  {provider.models && provider.models.length > 0 ? (
                                    <div className="flex flex-wrap gap-1 max-w-md">
                                      {provider.models.slice(0, 3).map((model: string) => (
                                        <Badge key={model} variant="outline" className="text-xs">
                                          {model}
                                        </Badge>
                                      ))}
                                      {provider.models.length > 3 && (
                                        <Badge variant="outline" className="text-xs">
                                          +{provider.models.length - 3} more
                                        </Badge>
                                      )}
                                    </div>
                                  ) : (
                                    <span className="text-muted-foreground text-sm">-</span>
                                  )}
                                </TableCell>
                                <TableCell>
                                  {override ? (
                                    <div className="space-y-1">
                                      <Badge variant="outline" className="text-xs">
                                        Override {override.is_enabled === false ? 'disabled' : 'active'}
                                      </Badge>
                                      {override.allowed_models?.length ? (
                                        <div className="text-xs text-muted-foreground">
                                          {override.allowed_models.length} models allowlisted
                                        </div>
                                      ) : null}
                                      {override.api_key_hint ? (
                                        <div className="text-xs text-muted-foreground">
                                          Key • ****{override.api_key_hint}
                                        </div>
                                      ) : null}
                                    </div>
                                  ) : (
                                    <span className="text-muted-foreground text-sm">-</span>
                                  )}
                                </TableCell>
                                <TableCell className="text-right">
                                  <div className="flex justify-end gap-2">
                                    <Button
                                      variant="ghost"
                                      size="sm"
                                      onClick={() => openOverrideDialog(provider)}
                                      title="Manage override"
                                    >
                                      <Settings className="h-4 w-4" />
                                    </Button>
                                    <Button
                                      variant="ghost"
                                      size="sm"
                                      onClick={() => handleTestProvider(provider)}
                                      disabled={testingProvider === provider.name}
                                      title="Test connectivity"
                                    >
                                      <Activity className={`h-4 w-4 ${testingProvider === provider.name ? 'animate-spin' : ''}`} />
                                    </Button>
                                    {docsUrl ? (
                                      <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => window.open(docsUrl, '_blank')}
                                        title="Open documentation"
                                      >
                                        <ExternalLink className="h-4 w-4" />
                                      </Button>
                                    ) : null}
                                  </div>
                                </TableCell>
                              </TableRow>
                            );
                          })}
                        </TableBody>
                      </Table>
                    )}
                  </CardContent>
                </Card>
              </TabsContent>

              {/* User BYOK Tab */}
              <TabsContent value="user-byok">
                <div className="grid gap-6 lg:grid-cols-3">
                  {/* User Selection */}
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <User className="h-5 w-5" />
                        Select User
                      </CardTitle>
                      <CardDescription>Choose a user to manage their BYOK keys</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-4">
                        <div className="relative">
                          <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                          <Input
                            placeholder="Search users..."
                            value={byokState.userSearch}
                            onChange={(e) => updateByokState({ userSearch: e.target.value, userLimit: 20 })}
                            className="pl-8"
                          />
                        </div>
                        <div className="max-h-80 overflow-y-auto space-y-1">
                          {visibleUsers.map((user) => (
                            <Button
                              key={user.id}
                              variant={byokState.selectedUser?.id === user.id ? 'default' : 'ghost'}
                              className="w-full justify-start text-left"
                              onClick={() => loadUserByokKeys(user)}
                            >
                              <User className="mr-2 h-4 w-4" />
                              <div className="truncate">
                                <div className="font-medium">{user.username || user.email}</div>
                                {user.username && (
                                  <div className="text-xs opacity-70">{user.email}</div>
                                )}
                              </div>
                            </Button>
                          ))}
                          {filteredUsers.length === 0 && (
                            <p className="text-center text-muted-foreground py-4">No users found</p>
                          )}
                          {filteredUsers.length > byokState.userLimit && (
                            <div className="space-y-2 pt-2">
                              <Button
                                variant="outline"
                                size="sm"
                                className="w-full"
                                onClick={() => updateByokState({ userLimit: byokState.userLimit + 20 })}
                              >
                                Show more
                              </Button>
                              <p className="text-center text-xs text-muted-foreground">
                                Showing {byokState.userLimit} of {filteredUsers.length} users
                              </p>
                            </div>
                          )}
                        </div>
                      </div>
                    </CardContent>
                  </Card>

                  {/* User BYOK Keys */}
                  <Card className="lg:col-span-2">
                    <CardHeader className="flex flex-row items-center justify-between">
                      <div>
                        <CardTitle className="flex items-center gap-2">
                          <Key className="h-5 w-5" />
                          User BYOK Keys
                        </CardTitle>
                        <CardDescription>
                          {byokState.selectedUser
                            ? `Managing keys for ${byokState.selectedUser.email}`
                            : 'Select a user to view their BYOK keys'}
                        </CardDescription>
                      </div>
                      {byokState.selectedUser && (
                        <Button size="sm" onClick={() => openAddByokDialog('user')}>
                          <Plus className="mr-2 h-4 w-4" />
                          Add Key
                        </Button>
                      )}
                    </CardHeader>
                    <CardContent>
                      {!byokState.selectedUser ? (
                        <div className="text-center text-muted-foreground py-8">
                          <Key className="h-12 w-12 mx-auto mb-2 opacity-50" />
                          <p>Select a user to manage their BYOK keys</p>
                        </div>
                      ) : byokState.isLoading ? (
                        <div className="text-center text-muted-foreground py-8">Loading...</div>
                      ) : byokState.userKeys.length === 0 ? (
                        <div className="text-center text-muted-foreground py-8">
                          <Key className="h-12 w-12 mx-auto mb-2 opacity-50" />
                          <p>No BYOK keys configured for this user</p>
                          <Button size="sm" className="mt-4" onClick={() => openAddByokDialog('user')}>
                            <Plus className="mr-2 h-4 w-4" />
                            Add First Key
                          </Button>
                        </div>
                      ) : (
                        <ByokKeysTable
                          keys={byokState.userKeys}
                          onDelete={handleDeleteUserByok}
                          formatProviderName={formatProviderName}
                          deletingProvider={deletingUserByokProvider}
                        />
                      )}
                    </CardContent>
                  </Card>
                </div>
              </TabsContent>

              {/* Org BYOK Tab */}
              <TabsContent value="org-byok">
                <div className="grid gap-6 lg:grid-cols-3">
                  {/* Org Selection */}
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <Building2 className="h-5 w-5" />
                        Select Organization
                      </CardTitle>
                      <CardDescription>Choose an organization to manage BYOK keys</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="max-h-80 overflow-y-auto space-y-1">
                        {byokState.organizations.length === 0 ? (
                          <p className="text-center text-muted-foreground py-4">No organizations found</p>
                        ) : (
                          byokState.organizations.map((org) => (
                            <Button
                              key={org.id}
                              variant={byokState.selectedOrg?.id === org.id ? 'default' : 'ghost'}
                              className="w-full justify-start text-left"
                              onClick={() => loadOrgByokKeys(org)}
                            >
                              <Building2 className="mr-2 h-4 w-4" />
                              <div className="truncate">
                                <div className="font-medium">{org.name}</div>
                                {org.description && (
                                  <div className="text-xs opacity-70 truncate">{org.description}</div>
                                )}
                              </div>
                            </Button>
                          ))
                        )}
                      </div>
                    </CardContent>
                  </Card>

                  {/* Org BYOK Keys */}
                  <Card className="lg:col-span-2">
                    <CardHeader className="flex flex-row items-center justify-between">
                      <div>
                        <CardTitle className="flex items-center gap-2">
                          <Key className="h-5 w-5" />
                          Organization BYOK Keys
                        </CardTitle>
                        <CardDescription>
                          {byokState.selectedOrg
                            ? `Managing keys for ${byokState.selectedOrg.name}`
                            : 'Select an organization to view BYOK keys'}
                        </CardDescription>
                      </div>
                      {byokState.selectedOrg && (
                        <Button size="sm" onClick={() => openAddByokDialog('org')}>
                          <Plus className="mr-2 h-4 w-4" />
                          Add Key
                        </Button>
                      )}
                    </CardHeader>
                    <CardContent>
                      {!byokState.selectedOrg ? (
                        <div className="text-center text-muted-foreground py-8">
                          <Key className="h-12 w-12 mx-auto mb-2 opacity-50" />
                          <p>Select an organization to manage BYOK keys</p>
                        </div>
                      ) : byokState.isLoading ? (
                        <div className="text-center text-muted-foreground py-8">Loading...</div>
                      ) : byokState.orgKeys.length === 0 ? (
                        <div className="text-center text-muted-foreground py-8">
                          <Key className="h-12 w-12 mx-auto mb-2 opacity-50" />
                          <p>No BYOK keys configured for this organization</p>
                          <Button size="sm" className="mt-4" onClick={() => openAddByokDialog('org')}>
                            <Plus className="mr-2 h-4 w-4" />
                            Add First Key
                          </Button>
                        </div>
                      ) : (
                        <ByokKeysTable
                          keys={byokState.orgKeys}
                          onDelete={handleDeleteOrgByok}
                          formatProviderName={formatProviderName}
                          deletingProvider={deletingOrgByokProvider}
                        />
                      )}
                    </CardContent>
                  </Card>
                </div>

                {/* BYOK Info */}
                <Card className="mt-6">
                  <CardContent className="pt-6">
                    <div className="grid gap-4 md:grid-cols-2">
                      <div className="p-4 rounded-lg bg-muted/50">
                        <h4 className="font-semibold mb-2">User-Level Keys</h4>
                        <p className="text-sm text-muted-foreground">
                          Individual users can configure their own API keys for personal use.
                          These keys are encrypted and stored securely. User keys take precedence
                          over organization and system keys.
                        </p>
                      </div>
                      <div className="p-4 rounded-lg bg-muted/50">
                        <h4 className="font-semibold mb-2">Organization-Level Keys</h4>
                        <p className="text-sm text-muted-foreground">
                          Organizations can set shared API keys for all members.
                          These take precedence over system defaults but can be overridden by user keys.
                        </p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>
            </Tabs>
          </div>

        {/* Provider Override Dialog */}
        <Dialog
          open={overrideDialog.isOpen}
          onOpenChange={(open) => updateOverrideDialog({ isOpen: open })}
        >
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle>Provider Override</DialogTitle>
              <DialogDescription>
                {overrideDialog.provider
                  ? `Manage ${formatProviderName(overrideDialog.provider.name)} overrides`
                  : 'Manage provider overrides'}
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="flex items-center justify-between">
                <div>
                  <Label>Enable provider</Label>
                  <p className="text-xs text-muted-foreground">Disable to block usage across the system.</p>
                </div>
                <Checkbox
                  checked={overrideDialog.enabled}
                  onCheckedChange={(checked) => updateOverrideDialog({ enabled: Boolean(checked) })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="overrideDefaultModel">Default model</Label>
                <Input
                  id="overrideDefaultModel"
                  placeholder={overrideDialog.provider?.default_model || 'e.g. gpt-4o-mini'}
                  value={overrideDialog.defaultModel}
                  onChange={(e) => updateOverrideDialog({ defaultModel: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="overrideAllowedModels">Allowlisted models</Label>
                <Input
                  id="overrideAllowedModels"
                  placeholder="Comma-separated list (leave empty for all)"
                  value={overrideDialog.allowedModels}
                  onChange={(e) => updateOverrideDialog({ allowedModels: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="overrideBaseUrl">Base URL</Label>
                <Input
                  id="overrideBaseUrl"
                  placeholder="https://api.example.com"
                  value={overrideDialog.baseUrl}
                  onChange={(e) => updateOverrideDialog({ baseUrl: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="overrideApiKey">API key</Label>
                <Input
                  id="overrideApiKey"
                  type="password"
                  placeholder={overrideDialog.override?.api_key_hint ? `Stored (****${overrideDialog.override.api_key_hint})` : 'sk-...'}
                  value={overrideDialog.apiKey}
                  onChange={(e) => updateOverrideDialog({ apiKey: e.target.value })}
                />
                {overrideDialog.override?.api_key_hint && (
                  <p className="text-xs text-muted-foreground">
                    Stored key hint: ****{overrideDialog.override.api_key_hint}
                  </p>
                )}
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <Label>Clear stored API key</Label>
                  <p className="text-xs text-muted-foreground">Remove the stored key for this provider.</p>
                </div>
                <Checkbox
                  checked={overrideDialog.clearApiKey}
                  onCheckedChange={(checked) => updateOverrideDialog({ clearApiKey: Boolean(checked) })}
                  disabled={overrideDialog.apiKey.trim().length > 0}
                />
              </div>
            </div>
            <DialogFooter className="flex items-center justify-between sm:justify-between">
              <div className="flex gap-2">
                {overrideDialog.override && (
                  <Button
                    variant="destructive"
                    onClick={handleDeleteOverride}
                    disabled={overrideDialog.isDeleting || overrideDialog.isSaving}
                  >
                    Remove Override
                  </Button>
                )}
              </div>
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => updateOverrideDialog({ isOpen: false })}>
                  Cancel
                </Button>
                <Button onClick={handleSaveOverride} disabled={overrideDialog.isSaving}>
                  {overrideDialog.isSaving ? 'Saving...' : 'Save'}
                </Button>
              </div>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Add BYOK Dialog */}
        <Dialog
          open={addByokDialog.isOpen}
          onOpenChange={(open) => {
            if (!open) {
              updateAddByokDialog({
                isOpen: false,
                provider: '',
                customProviderName: '',
                apiKey: '',
                isAdding: false,
              });
            } else {
              updateAddByokDialog({ isOpen: true });
            }
          }}
        >
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Add BYOK Key</DialogTitle>
              <DialogDescription>
                {addByokDialog.mode === 'user' && byokState.selectedUser
                  ? `Add an API key for ${byokState.selectedUser.email}`
                  : addByokDialog.mode === 'org' && byokState.selectedOrg
                  ? `Add an API key for ${byokState.selectedOrg.name}`
                  : 'Add a new provider API key'}
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="provider">Provider</Label>
                <select
                  id="provider"
                  value={addByokDialog.provider}
                  onChange={(e) => {
                    const value = e.target.value;
                    updateAddByokDialog({ provider: value });
                    if (value !== 'other') {
                      updateAddByokDialog({ customProviderName: '' });
                    }
                  }}
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <option value="">Select a provider...</option>
                  {commonProviders.map((p) => (
                    <option key={p} value={p}>
                      {formatProviderName(p)}
                    </option>
                  ))}
                  <option value="other">Other (custom)</option>
                </select>
                {addByokDialog.provider === 'other' && (
                  <Input
                    placeholder="Enter provider name..."
                    value={addByokDialog.customProviderName}
                    onChange={(e) => updateAddByokDialog({ customProviderName: e.target.value })}
                    className="mt-2"
                  />
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="apiKey">API Key</Label>
                <Input
                  id="apiKey"
                  type="password"
                  placeholder="sk-..."
                  value={addByokDialog.apiKey}
                  onChange={(e) => updateAddByokDialog({ apiKey: e.target.value })}
                />
                <p className="text-xs text-muted-foreground">
                  The key will be encrypted before storage
                </p>
              </div>
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => updateAddByokDialog({
                  isOpen: false,
                  provider: '',
                  customProviderName: '',
                  apiKey: '',
                  isAdding: false,
                })}
              >
                Cancel
              </Button>
              <Button
                onClick={handleAddByok}
                disabled={
                  addByokDialog.isAdding ||
                  !canSubmitByok
                }
              >
                {addByokDialog.isAdding ? 'Adding...' : 'Add Key'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </ResponsiveLayout>
    </PermissionGuard>
  );
}
