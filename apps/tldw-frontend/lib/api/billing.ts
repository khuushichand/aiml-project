export type BillingPlan = {
  id?: number | null
  name: string
  display_name: string
  description?: string | null
  price_usd_monthly?: number
  price_usd_yearly?: number
  limits?: Record<string, unknown>
  is_active?: boolean
  is_public?: boolean
}

export type BillingPlanListResponse = {
  plans: BillingPlan[]
}

export type BillingSubscription = {
  org_id: number
  plan_name: string
  plan_display_name: string
  status: string
  billing_cycle?: string | null
  current_period_end?: string | null
  trial_end?: string | null
  cancel_at_period_end?: boolean
  limits?: Record<string, unknown>
}

export type BillingUsage = {
  org_id: number
  plan_name: string
  limits: Record<string, number | boolean | null>
  usage: Record<string, number>
  limit_checks: Record<
    string,
    {
      usage?: number
      limit?: number | null
      exceeded?: boolean
      warning?: boolean
    }
  >
  has_warnings: boolean
  has_exceeded: boolean
}

export type BillingInvoice = {
  id: number
  org_id: number
  stripe_invoice_id?: string | null
  amount_cents: number
  amount_display?: string
  currency?: string
  status: string
  description?: string | null
  invoice_pdf_url?: string | null
  created_at?: string | null
}

export type BillingInvoiceListResponse = {
  items: BillingInvoice[]
  total: number
}

export type CheckoutSessionResponse = {
  session_id: string
  url: string
}

export type PortalSessionResponse = {
  session_id: string
  url: string
}

type RequestJsonOptions = {
  method?: "GET" | "POST"
  body?: Record<string, unknown>
  allowNotFound?: boolean
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

async function requestJson<T>(
  path: string,
  options: RequestJsonOptions = {}
): Promise<T | null> {
  const { method = "GET", body, allowNotFound = false } = options
  const response = await fetch(path, {
    method,
    headers: {
      Accept: "application/json",
      ...(body
        ? {
            "Content-Type": "application/json"
          }
        : {})
    },
    ...(body
      ? {
          body: JSON.stringify(body)
        }
      : {})
  })

  if (allowNotFound && response.status === 404) {
    return null
  }

  if (!response.ok) {
    throw new Error(await getErrorMessage(response))
  }

  return await response.json()
}

export async function fetchSubscription(): Promise<BillingSubscription | null> {
  return await requestJson<BillingSubscription>("/api/proxy/billing/subscription", {
    allowNotFound: true
  })
}

export async function fetchUsage(): Promise<BillingUsage | null> {
  return await requestJson<BillingUsage>("/api/proxy/billing/usage", {
    allowNotFound: true
  })
}

export async function fetchInvoices(): Promise<BillingInvoiceListResponse> {
  const payload = await requestJson<BillingInvoiceListResponse>("/api/proxy/billing/invoices", {
    allowNotFound: true
  })
  return payload ?? { items: [], total: 0 }
}

export async function fetchPlans(): Promise<BillingPlanListResponse> {
  const payload = await requestJson<BillingPlanListResponse>("/api/proxy/billing/plans")
  return payload ?? { plans: [] }
}

export async function createCheckoutSession(input: {
  planName: string
  billingCycle: "monthly" | "yearly"
  successUrl: string
  cancelUrl: string
}): Promise<CheckoutSessionResponse> {
  const payload = await requestJson<CheckoutSessionResponse>("/api/proxy/billing/checkout", {
    method: "POST",
    body: {
      plan_name: input.planName,
      billing_cycle: input.billingCycle,
      success_url: input.successUrl,
      cancel_url: input.cancelUrl
    }
  })

  if (!payload) {
    throw new Error("Checkout is unavailable right now.")
  }

  return payload
}

export async function createPortalSession(input: {
  returnUrl: string
}): Promise<PortalSessionResponse> {
  const payload = await requestJson<PortalSessionResponse>("/api/proxy/billing/portal", {
    method: "POST",
    body: {
      return_url: input.returnUrl
    }
  })

  if (!payload) {
    throw new Error("Billing portal is unavailable right now.")
  }

  return payload
}
