'use client';

import type { Dispatch, FormEvent, SetStateAction } from 'react';
import { UserPlus } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
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

type CreateUserFormState = {
  username: string;
  email: string;
  password: string;
  role: string;
  is_active: boolean;
  is_verified: boolean;
};

type CreateUserDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  error: string;
  form: CreateUserFormState;
  setForm: Dispatch<SetStateAction<CreateUserFormState>>;
  creating: boolean;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
};

export function CreateUserDialog({
  open,
  onOpenChange,
  error,
  form,
  setForm,
  creating,
  onSubmit,
}: CreateUserDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogTrigger asChild>
        <Button size="sm" variant="outline">
          <UserPlus className="mr-2 h-4 w-4" />
          Create user
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create user</DialogTitle>
          <DialogDescription>
            Create a user directly as an admin. Provide a temporary password.
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
              <Label htmlFor="create-user-username">Username</Label>
              <Input
                id="create-user-username"
                value={form.username}
                onChange={(event) => setForm((prev) => ({
                  ...prev,
                  username: event.target.value,
                }))}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="create-user-email">Email</Label>
              <Input
                id="create-user-email"
                type="email"
                value={form.email}
                onChange={(event) => setForm((prev) => ({
                  ...prev,
                  email: event.target.value,
                }))}
                required
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="create-user-password">Password</Label>
            <Input
              id="create-user-password"
              type="password"
              value={form.password}
              onChange={(event) => setForm((prev) => ({
                ...prev,
                password: event.target.value,
              }))}
              required
            />
            <p className="text-xs text-muted-foreground">Minimum 10 characters.</p>
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="create-user-role">Role</Label>
              <Select
                id="create-user-role"
                value={form.role}
                onChange={(event) => setForm((prev) => ({
                  ...prev,
                  role: event.target.value,
                }))}
              >
                <option value="user">User</option>
                <option value="admin">Admin</option>
                <option value="service">Service</option>
              </Select>
            </div>
            <div className="space-y-2">
              <Label className="block">Status</Label>
              <div className="space-y-2">
                <label className="flex items-center gap-2 text-sm">
                  <Checkbox
                    id="create-user-active"
                    checked={form.is_active}
                    onCheckedChange={(checked) => setForm((prev) => ({
                      ...prev,
                      is_active: checked,
                    }))}
                  />
                  Active
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <Checkbox
                    id="create-user-verified"
                    checked={form.is_verified}
                    onCheckedChange={(checked) => setForm((prev) => ({
                      ...prev,
                      is_verified: checked,
                    }))}
                  />
                  Verified
                </label>
              </div>
            </div>
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
              Create user
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
