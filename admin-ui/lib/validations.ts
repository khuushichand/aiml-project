import { z } from 'zod';

// Login form validation
export const loginSchema = z.object({
  username: z
    .string()
    .min(1, 'Username is required')
    .min(3, 'Username must be at least 3 characters'),
  password: z
    .string()
    .min(1, 'Password is required')
    .min(6, 'Password must be at least 6 characters'),
});

export type LoginFormData = z.infer<typeof loginSchema>;

// API key login validation
export const apiKeySchema = z.object({
  apiKey: z
    .string()
    .min(1, 'API key is required')
    .min(10, 'API key seems too short'),
});

export type ApiKeyFormData = z.infer<typeof apiKeySchema>;

// Create role validation
export const createRoleSchema = z.object({
  name: z
    .string()
    .min(1, 'Role name is required')
    .min(2, 'Role name must be at least 2 characters')
    .max(50, 'Role name must be less than 50 characters')
    .regex(/^[a-z_]+$/, 'Role name must be lowercase with underscores only'),
  description: z
    .string()
    .max(200, 'Description must be less than 200 characters')
    .optional(),
});

export type CreateRoleFormData = z.infer<typeof createRoleSchema>;

// Create permission validation
export const createPermissionSchema = z.object({
  name: z
    .string()
    .min(1, 'Permission name is required')
    .min(3, 'Permission name must be at least 3 characters')
    .max(50, 'Permission name must be less than 50 characters')
    .regex(/^[a-z_:]+$/, 'Permission name must be lowercase with underscores and colons only (e.g., read:users)'),
  description: z
    .string()
    .max(200, 'Description must be less than 200 characters')
    .optional(),
});

export type CreatePermissionFormData = z.infer<typeof createPermissionSchema>;

// Create organization validation
export const createOrganizationSchema = z.object({
  name: z
    .string()
    .min(1, 'Organization name is required')
    .min(2, 'Organization name must be at least 2 characters')
    .max(100, 'Organization name must be less than 100 characters'),
  slug: z
    .string()
    .min(1, 'Slug is required')
    .min(2, 'Slug must be at least 2 characters')
    .max(50, 'Slug must be less than 50 characters')
    .regex(/^[a-z0-9-]+$/, 'Slug must be lowercase letters, numbers, and hyphens only'),
  description: z
    .string()
    .max(500, 'Description must be less than 500 characters')
    .optional(),
});

export type CreateOrganizationFormData = z.infer<typeof createOrganizationSchema>;

// Create team validation
export const createTeamSchema = z.object({
  name: z
    .string()
    .min(1, 'Team name is required')
    .min(2, 'Team name must be at least 2 characters')
    .max(100, 'Team name must be less than 100 characters'),
  description: z
    .string()
    .max(500, 'Description must be less than 500 characters')
    .optional(),
});

export type CreateTeamFormData = z.infer<typeof createTeamSchema>;

// Create API key validation
export const createApiKeySchema = z.object({
  name: z
    .string()
    .min(1, 'API key name is required')
    .min(2, 'Name must be at least 2 characters')
    .max(100, 'Name must be less than 100 characters'),
  scope: z
    .string()
    .min(1, 'Scope is required'),
  expires_at: z
    .string()
    .optional(),
});

export type CreateApiKeyFormData = z.infer<typeof createApiKeySchema>;

// User update validation
export const updateUserSchema = z.object({
  username: z
    .string()
    .min(1, 'Username is required')
    .min(3, 'Username must be at least 3 characters')
    .max(50, 'Username must be less than 50 characters'),
  email: z
    .string()
    .min(1, 'Email is required')
    .email('Invalid email address'),
  role: z
    .string()
    .min(1, 'Role is required'),
  is_active: z.boolean(),
  storage_quota_mb: z
    .number()
    .min(0, 'Storage quota must be non-negative')
    .max(1000000, 'Storage quota is too large'),
});

export type UpdateUserFormData = z.infer<typeof updateUserSchema>;

// BYOK key validation
export const createByokKeySchema = z.object({
  provider: z
    .string()
    .min(1, 'Provider is required'),
  api_key: z
    .string()
    .min(1, 'API key is required')
    .min(10, 'API key seems too short'),
});

export type CreateByokKeyFormData = z.infer<typeof createByokKeySchema>;

// Watchlist validation
export const createWatchlistSchema = z.object({
  name: z
    .string()
    .min(1, 'Name is required')
    .min(2, 'Name must be at least 2 characters')
    .max(100, 'Name must be less than 100 characters'),
  description: z
    .string()
    .max(500, 'Description must be less than 500 characters')
    .optional(),
  target: z
    .string()
    .min(1, 'Target is required'),
  type: z
    .string()
    .min(1, 'Type is required'),
  threshold: z
    .number()
    .min(0, 'Threshold must be non-negative'),
});

export type CreateWatchlistFormData = z.infer<typeof createWatchlistSchema>;

// Invite member validation
export const inviteMemberSchema = z.object({
  email: z
    .string()
    .min(1, 'Email is required')
    .email('Invalid email address'),
  role: z
    .string()
    .min(1, 'Role is required'),
});

export type InviteMemberFormData = z.infer<typeof inviteMemberSchema>;
