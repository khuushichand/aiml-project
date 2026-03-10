import { useForm, FormProvider } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Form, FormField, FormInput, FormSelect } from '@/components/ui/form';

const apiKeySchema = z.object({
  name: z.string().min(1, 'Key name is required'),
  scope: z.enum(['read', 'write', 'admin']),
  expires_days: z.preprocess(
    (value) => Number(value),
    z.number().int().min(1, 'Minimum 1 day').max(365, 'Maximum 365 days')
  ),
});

type ApiKeyFormInput = z.input<typeof apiKeySchema>;
export type ApiKeyFormData = z.output<typeof apiKeySchema>;

type ApiKeyCreateFormProps = {
  onSubmit: (data: ApiKeyFormData) => Promise<void> | void;
  onCancel: () => void;
  isSubmitting?: boolean;
};

const defaultValues: ApiKeyFormInput = {
  name: '',
  scope: 'read',
  expires_days: 90,
};

export const ApiKeyCreateForm = ({
  onSubmit,
  onCancel,
  isSubmitting = false,
}: ApiKeyCreateFormProps) => {
  const form = useForm<ApiKeyFormInput, unknown, ApiKeyFormData>({
    resolver: zodResolver(apiKeySchema),
    defaultValues,
  });

  const expiresField = form.register('expires_days');
  const expiresError = form.formState.errors.expires_days;

  const handleSubmit = form.handleSubmit(async (data) => {
    await onSubmit(data);
    form.reset(defaultValues);
  });

  const handleCancel = () => {
    form.reset(defaultValues);
    onCancel();
  };

  return (
    <Card className="mb-6">
      <CardHeader>
        <CardTitle>Create API Key</CardTitle>
        <CardDescription>Generate a new API key for this user</CardDescription>
      </CardHeader>
      <CardContent>
        <FormProvider {...form}>
          <Form onSubmit={handleSubmit}>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <FormInput<ApiKeyFormData>
                name="name"
                label="Key Name"
                placeholder="e.g., Production API"
                required
              />

              <FormSelect<ApiKeyFormData>
                name="scope"
                label="Scope"
                options={[
                  { value: 'read', label: 'Read Only' },
                  { value: 'write', label: 'Read & Write' },
                  { value: 'admin', label: 'Admin' },
                ]}
              />

              <FormField<ApiKeyFormData> name="expires_days" label="Expires In (days)">
                <Input
                  id="expires"
                  type="number"
                  min="1"
                  max="365"
                  aria-invalid={expiresError ? 'true' : undefined}
                  aria-describedby={expiresError ? 'expires_days-error' : undefined}
                  {...expiresField}
                  onChange={(e) => expiresField.onChange(e)}
                />
              </FormField>
            </div>

            <div className="flex gap-2">
              <Button type="submit" loading={isSubmitting} loadingText="Creating...">
                Create Key
              </Button>
              <Button type="button" variant="outline" onClick={handleCancel} disabled={isSubmitting}>
                Cancel
              </Button>
            </div>
          </Form>
        </FormProvider>
      </CardContent>
    </Card>
  );
};
