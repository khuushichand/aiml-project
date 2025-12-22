import type { Dispatch, FormEvent, SetStateAction } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

type ApiKeyFormData = {
  name: string;
  scope: string;
  expires_days: number;
};

type ApiKeyCreateFormProps = {
  formData: ApiKeyFormData;
  onFormDataChange: Dispatch<SetStateAction<ApiKeyFormData>>;
  onSubmit: (event: FormEvent) => void;
  onCancel: () => void;
};

export const ApiKeyCreateForm = ({
  formData,
  onFormDataChange,
  onSubmit,
  onCancel,
}: ApiKeyCreateFormProps) => (
  <Card className="mb-6">
    <CardHeader>
      <CardTitle>Create API Key</CardTitle>
      <CardDescription>Generate a new API key for this user</CardDescription>
    </CardHeader>
    <CardContent>
      <form onSubmit={onSubmit} className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="space-y-2">
            <Label htmlFor="name">Key Name</Label>
            <Input
              id="name"
              placeholder="e.g., Production API"
              value={formData.name}
              onChange={(e) => onFormDataChange({ ...formData, name: e.target.value })}
              required
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="scope">Scope</Label>
            <Select
              id="scope"
              value={formData.scope}
              onChange={(e) => onFormDataChange({ ...formData, scope: e.target.value })}
            >
              <option value="read">Read Only</option>
              <option value="write">Read & Write</option>
              <option value="admin">Admin</option>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="expires">Expires In (days)</Label>
            <Input
              id="expires"
              type="number"
              min="1"
              max="365"
              value={formData.expires_days}
              onChange={(e) =>
                onFormDataChange({
                  ...formData,
                  expires_days: parseInt(e.target.value, 10) || 90,
                })
              }
            />
          </div>
        </div>

        <div className="flex gap-2">
          <Button type="submit">Create Key</Button>
          <Button type="button" variant="outline" onClick={onCancel}>
            Cancel
          </Button>
        </div>
      </form>
    </CardContent>
  </Card>
);
