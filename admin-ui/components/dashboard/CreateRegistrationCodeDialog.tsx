'use client';

import type { Dispatch, FormEvent, SetStateAction } from 'react';
import { Plus } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';

type RegistrationFormState = {
  max_uses: number;
  expiry_days: number;
  role_to_grant: string;
};

type CreateRegistrationCodeDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  error: string;
  form: RegistrationFormState;
  setForm: Dispatch<SetStateAction<RegistrationFormState>>;
  creating: boolean;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
};

export function CreateRegistrationCodeDialog({
  open,
  onOpenChange,
  error,
  form,
  setForm,
  creating,
  onSubmit,
}: CreateRegistrationCodeDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogTrigger asChild>
        <Button size="sm">
          <Plus className="mr-2 h-4 w-4" />
          New Code
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create registration code</DialogTitle>
          <DialogDescription>
            Share a code to allow new users to register with a predefined role.
          </DialogDescription>
        </DialogHeader>
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        <form onSubmit={onSubmit} className="space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="reg-max-uses">Max uses</Label>
              <Input
                id="reg-max-uses"
                type="number"
                min={1}
                max={100}
                value={form.max_uses}
                onChange={(event) => setForm((prev) => ({
                  ...prev,
                  max_uses: Number(event.target.value || 1),
                }))}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="reg-expiry-days">Expiry (days)</Label>
              <Input
                id="reg-expiry-days"
                type="number"
                min={1}
                max={365}
                value={form.expiry_days}
                onChange={(event) => setForm((prev) => ({
                  ...prev,
                  expiry_days: Number(event.target.value || 1),
                }))}
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="reg-role">Role</Label>
            <Select
              id="reg-role"
              value={form.role_to_grant}
              onChange={(event) => setForm((prev) => ({
                ...prev,
                role_to_grant: event.target.value,
              }))}
            >
              <option value="user">User</option>
              <option value="admin">Admin</option>
              <option value="service">Service</option>
            </Select>
          </div>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={creating}
            >
              Cancel
            </Button>
            <Button type="submit" loading={creating} loadingText="Creating…">
              Create code
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
