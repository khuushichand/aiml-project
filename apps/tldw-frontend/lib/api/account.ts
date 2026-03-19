export type AccountIdentity = {
  id?: number | string
  username?: string
  email?: string
  role?: string
  is_active?: boolean
  is_verified?: boolean
  created_at?: string | null
  last_login?: string | null
  storage_quota_mb?: number | null
  storage_used_mb?: number | null
}

export type AccountMembership = {
  org_id?: number
  org_name?: string
  role?: string
  is_active?: boolean
  is_default?: boolean
}

export type AccountSecurity = {
  verified?: boolean
  mfa_enabled?: boolean
  last_password_change_at?: string | null
  login_methods?: string[]
}

export type AccountQuotas = {
  storage_quota_mb?: number | null
  storage_used_mb?: number | null
  [key: string]: unknown
}

export type AccountProfileResponse = {
  profile_version?: string
  catalog_version?: string
  user?: AccountIdentity
  memberships?: AccountMembership[]
  security?: AccountSecurity
  quotas?: AccountQuotas
  section_errors?: Record<string, string>
}

const getErrorMessage = async (response: Response): Promise<string> => {
  try {
    const payload = await response.json()
    if (typeof payload?.detail === "string" && payload.detail.trim().length > 0) {
      return payload.detail
    }
    if (typeof payload?.message === "string" && payload.message.trim().length > 0) {
      return payload.message
    }
  } catch {
    // Fall back to the response status text below.
  }

  return `Request failed (${response.status})`
}

export async function fetchCurrentUserProfile(): Promise<AccountProfileResponse> {
  const response = await fetch("/api/proxy/users/me/profile", {
    method: "GET",
    headers: {
      Accept: "application/json"
    }
  })

  if (!response.ok) {
    throw new Error(await getErrorMessage(response))
  }

  return await response.json()
}
