'use client';

import { useEffect, useState } from 'react';
import ProtectedRoute from '@/components/ProtectedRoute';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useConfirm } from '@/components/ui/confirm-dialog';
import { Cpu, RefreshCw, CheckCircle, XCircle, Key, ExternalLink, Plus, Trash2, Search, Building2, User } from 'lucide-react';
import { api } from '@/lib/api-client';
import { LLMProvider, User as UserType, Organization } from '@/types';

interface ByokKey {
  id?: string;
  provider: string;
  key_hint?: string;
  created_at?: string;
}

export default function ProvidersPage() {
  const confirm = useConfirm();
  const [providers, setProviders] = useState<LLMProvider[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // BYOK management state
  const [users, setUsers] = useState<UserType[]>([]);
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [selectedUser, setSelectedUser] = useState<UserType | null>(null);
  const [selectedOrg, setSelectedOrg] = useState<Organization | null>(null);
  const [userByokKeys, setUserByokKeys] = useState<ByokKey[]>([]);
  const [orgByokKeys, setOrgByokKeys] = useState<ByokKey[]>([]);
  const [loadingByok, setLoadingByok] = useState(false);
  const [userSearch, setUserSearch] = useState('');

  // Add BYOK dialog
  const [showAddByok, setShowAddByok] = useState(false);
  const [addByokMode, setAddByokMode] = useState<'user' | 'org'>('user');
  const [newByokProvider, setNewByokProvider] = useState('');
  const [newByokKey, setNewByokKey] = useState('');
  const [addingByok, setAddingByok] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      setError('');

      const [providersData, usersData, orgsData] = await Promise.allSettled([
        api.getLLMProviders(),
        api.getUsers(),
        api.getOrganizations(),
      ]);

      if (providersData.status === 'fulfilled') {
        let providersArray: LLMProvider[] = [];
        if (Array.isArray(providersData.value)) {
          providersArray = providersData.value;
        } else if (providersData.value && typeof providersData.value === 'object') {
          providersArray = Object.entries(providersData.value).map(([name, value]: [string, any]) => ({
            name,
            enabled: value.enabled ?? true,
            models: value.models || [],
            ...value,
          }));
        }
        setProviders(providersArray);
      }

      if (usersData.status === 'fulfilled') {
        setUsers(Array.isArray(usersData.value) ? usersData.value : usersData.value?.users || []);
      }

      if (orgsData.status === 'fulfilled') {
        setOrganizations(Array.isArray(orgsData.value) ? orgsData.value : []);
      }
    } catch (err: any) {
      console.error('Failed to load data:', err);
      setError(err.message || 'Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const loadUserByokKeys = async (user: UserType) => {
    setSelectedUser(user);
    setLoadingByok(true);
    try {
      const keys = await api.getUserByokKeys(user.id.toString());
      setUserByokKeys(Array.isArray(keys) ? keys : []);
    } catch (err: any) {
      console.error('Failed to load user BYOK keys:', err);
      setUserByokKeys([]);
    } finally {
      setLoadingByok(false);
    }
  };

  const loadOrgByokKeys = async (org: Organization) => {
    setSelectedOrg(org);
    setLoadingByok(true);
    try {
      const keys = await api.getOrgByokKeys(org.id.toString());
      setOrgByokKeys(Array.isArray(keys) ? keys : []);
    } catch (err: any) {
      console.error('Failed to load org BYOK keys:', err);
      setOrgByokKeys([]);
    } finally {
      setLoadingByok(false);
    }
  };

  const handleAddByok = async () => {
    if (!newByokProvider.trim() || !newByokKey.trim()) {
      setError('Provider and API key are required');
      return;
    }

    setAddingByok(true);
    setError('');
    try {
      const data = {
        provider: newByokProvider.trim().toLowerCase(),
        api_key: newByokKey.trim(),
      };

      if (addByokMode === 'user' && selectedUser) {
        await api.createUserByokKey(selectedUser.id.toString(), data);
        await loadUserByokKeys(selectedUser);
        setSuccess(`BYOK key added for ${selectedUser.email}`);
      } else if (addByokMode === 'org' && selectedOrg) {
        await api.createOrgByokKey(selectedOrg.id.toString(), data);
        await loadOrgByokKeys(selectedOrg);
        setSuccess(`BYOK key added for ${selectedOrg.name}`);
      }

      setShowAddByok(false);
      setNewByokProvider('');
      setNewByokKey('');
    } catch (err: any) {
      console.error('Failed to add BYOK key:', err);
      setError(err.message || 'Failed to add BYOK key');
    } finally {
      setAddingByok(false);
    }
  };

  const handleDeleteUserByok = async (provider: string) => {
    if (!selectedUser) return;

    const confirmed = await confirm({
      title: 'Delete API Key',
      message: `Delete ${provider} key for ${selectedUser.email}?`,
      confirmText: 'Delete',
      variant: 'danger',
      icon: 'key',
    });
    if (!confirmed) return;

    try {
      setError('');
      await api.deleteUserByokKey(selectedUser.id.toString(), provider);
      await loadUserByokKeys(selectedUser);
      setSuccess(`Deleted ${provider} key for ${selectedUser.email}`);
    } catch (err: any) {
      console.error('Failed to delete BYOK key:', err);
      setError(err.message || 'Failed to delete BYOK key');
    }
  };

  const handleDeleteOrgByok = async (provider: string) => {
    if (!selectedOrg) return;

    const confirmed = await confirm({
      title: 'Delete API Key',
      message: `Delete ${provider} key for ${selectedOrg.name}?`,
      confirmText: 'Delete',
      variant: 'danger',
      icon: 'key',
    });
    if (!confirmed) return;

    try {
      setError('');
      await api.deleteOrgByokKey(selectedOrg.id.toString(), provider);
      await loadOrgByokKeys(selectedOrg);
      setSuccess(`Deleted ${provider} key for ${selectedOrg.name}`);
    } catch (err: any) {
      console.error('Failed to delete BYOK key:', err);
      setError(err.message || 'Failed to delete BYOK key');
    }
  };

  const openAddByokDialog = (mode: 'user' | 'org') => {
    setAddByokMode(mode);
    setNewByokProvider('');
    setNewByokKey('');
    setShowAddByok(true);
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

  const filteredUsers = users.filter(
    (u) =>
      userSearch === '' ||
      u.email?.toLowerCase().includes(userSearch.toLowerCase()) ||
      u.username?.toLowerCase().includes(userSearch.toLowerCase())
  );

  const enabledProviders = providers.filter((p) => p.enabled);
  const disabledProviders = providers.filter((p) => !p.enabled);

  // Common provider options for BYOK
  const commonProviders = ['openai', 'anthropic', 'google', 'cohere', 'groq', 'mistral', 'deepseek', 'openrouter'];

  return (
    <ProtectedRoute>
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

            {error && (
              <Alert variant="destructive" className="mb-6">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            {success && (
              <Alert className="mb-6 bg-green-50 border-green-200">
                <AlertDescription className="text-green-800">{success}</AlertDescription>
              </Alert>
            )}

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
                          and local inference servers. Provider API keys can be configured in the server's config.txt
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
                            <TableHead className="text-right">Documentation</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {providers.map((provider) => {
                            const docsUrl = getProviderDocs(provider.name);
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
                                <TableCell className="text-right">
                                  {docsUrl ? (
                                    <Button
                                      variant="ghost"
                                      size="sm"
                                      onClick={() => window.open(docsUrl, '_blank')}
                                    >
                                      <ExternalLink className="h-4 w-4" />
                                    </Button>
                                  ) : (
                                    <span className="text-muted-foreground">-</span>
                                  )}
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
                            value={userSearch}
                            onChange={(e) => setUserSearch(e.target.value)}
                            className="pl-8"
                          />
                        </div>
                        <div className="max-h-80 overflow-y-auto space-y-1">
                          {filteredUsers.slice(0, 20).map((user) => (
                            <Button
                              key={user.id}
                              variant={selectedUser?.id === user.id ? 'default' : 'ghost'}
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
                          {filteredUsers.length > 20 && (
                            <p className="text-center text-xs text-muted-foreground py-2">
                              Showing 20 of {filteredUsers.length} users
                            </p>
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
                          {selectedUser
                            ? `Managing keys for ${selectedUser.email}`
                            : 'Select a user to view their BYOK keys'}
                        </CardDescription>
                      </div>
                      {selectedUser && (
                        <Button size="sm" onClick={() => openAddByokDialog('user')}>
                          <Plus className="mr-2 h-4 w-4" />
                          Add Key
                        </Button>
                      )}
                    </CardHeader>
                    <CardContent>
                      {!selectedUser ? (
                        <div className="text-center text-muted-foreground py-8">
                          <Key className="h-12 w-12 mx-auto mb-2 opacity-50" />
                          <p>Select a user to manage their BYOK keys</p>
                        </div>
                      ) : loadingByok ? (
                        <div className="text-center text-muted-foreground py-8">Loading...</div>
                      ) : userByokKeys.length === 0 ? (
                        <div className="text-center text-muted-foreground py-8">
                          <Key className="h-12 w-12 mx-auto mb-2 opacity-50" />
                          <p>No BYOK keys configured for this user</p>
                          <Button size="sm" className="mt-4" onClick={() => openAddByokDialog('user')}>
                            <Plus className="mr-2 h-4 w-4" />
                            Add First Key
                          </Button>
                        </div>
                      ) : (
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
                            {userByokKeys.map((key) => (
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
                                    onClick={() => handleDeleteUserByok(key.provider)}
                                  >
                                    <Trash2 className="h-4 w-4 text-red-500" />
                                  </Button>
                                </TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
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
                        {organizations.length === 0 ? (
                          <p className="text-center text-muted-foreground py-4">No organizations found</p>
                        ) : (
                          organizations.map((org) => (
                            <Button
                              key={org.id}
                              variant={selectedOrg?.id === org.id ? 'default' : 'ghost'}
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
                          {selectedOrg
                            ? `Managing keys for ${selectedOrg.name}`
                            : 'Select an organization to view BYOK keys'}
                        </CardDescription>
                      </div>
                      {selectedOrg && (
                        <Button size="sm" onClick={() => openAddByokDialog('org')}>
                          <Plus className="mr-2 h-4 w-4" />
                          Add Key
                        </Button>
                      )}
                    </CardHeader>
                    <CardContent>
                      {!selectedOrg ? (
                        <div className="text-center text-muted-foreground py-8">
                          <Key className="h-12 w-12 mx-auto mb-2 opacity-50" />
                          <p>Select an organization to manage BYOK keys</p>
                        </div>
                      ) : loadingByok ? (
                        <div className="text-center text-muted-foreground py-8">Loading...</div>
                      ) : orgByokKeys.length === 0 ? (
                        <div className="text-center text-muted-foreground py-8">
                          <Key className="h-12 w-12 mx-auto mb-2 opacity-50" />
                          <p>No BYOK keys configured for this organization</p>
                          <Button size="sm" className="mt-4" onClick={() => openAddByokDialog('org')}>
                            <Plus className="mr-2 h-4 w-4" />
                            Add First Key
                          </Button>
                        </div>
                      ) : (
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
                            {orgByokKeys.map((key) => (
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
                                    onClick={() => handleDeleteOrgByok(key.provider)}
                                  >
                                    <Trash2 className="h-4 w-4 text-red-500" />
                                  </Button>
                                </TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
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

        {/* Add BYOK Dialog */}
        <Dialog open={showAddByok} onOpenChange={setShowAddByok}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Add BYOK Key</DialogTitle>
              <DialogDescription>
                {addByokMode === 'user' && selectedUser
                  ? `Add an API key for ${selectedUser.email}`
                  : addByokMode === 'org' && selectedOrg
                  ? `Add an API key for ${selectedOrg.name}`
                  : 'Add a new provider API key'}
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="provider">Provider</Label>
                <select
                  id="provider"
                  value={newByokProvider}
                  onChange={(e) => setNewByokProvider(e.target.value)}
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
                {newByokProvider === 'other' && (
                  <Input
                    placeholder="Enter provider name..."
                    value=""
                    onChange={(e) => setNewByokProvider(e.target.value)}
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
                  value={newByokKey}
                  onChange={(e) => setNewByokKey(e.target.value)}
                />
                <p className="text-xs text-muted-foreground">
                  The key will be encrypted before storage
                </p>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowAddByok(false)}>
                Cancel
              </Button>
              <Button onClick={handleAddByok} disabled={addingByok || !newByokProvider || !newByokKey}>
                {addingByok ? 'Adding...' : 'Add Key'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </ResponsiveLayout>
    </ProtectedRoute>
  );
}
