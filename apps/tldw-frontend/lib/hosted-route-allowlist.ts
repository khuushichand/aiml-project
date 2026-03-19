const HOSTED_ALLOWED_ROUTES = [
  "/",
  "/signup",
  "/login",
  "/auth/verify-email",
  "/auth/reset-password",
  "/auth/magic-link",
  "/account",
  "/billing",
  "/billing/success",
  "/billing/cancel",
  "/chat",
  "/media",
  "/knowledge",
  "/collections"
] as const

const HOSTED_ALLOWED_ROUTE_SET = new Set<string>(HOSTED_ALLOWED_ROUTES)

export const getHostedAllowedRoutes = (): string[] => [
  ...HOSTED_ALLOWED_ROUTES
]

export const isHostedAllowedRoute = (route: string): boolean =>
  HOSTED_ALLOWED_ROUTE_SET.has(route)
