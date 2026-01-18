import React from "react"
import NextLink from "next/link"
import { useRouter } from "next/router"

type NextLinkProps = React.ComponentProps<typeof NextLink>

type LinkProps = Omit<NextLinkProps, "href"> & {
  to?: string
  href?: NextLinkProps["href"]
}

type NavLinkClassName =
  | string
  | ((props: { isActive: boolean }) => string | undefined)

type NavLinkProps = Omit<LinkProps, "className"> & {
  className?: NavLinkClassName
}

type NavigateOptions = {
  replace?: boolean
  state?: unknown
}

export const Link: React.FC<LinkProps> = ({ to, href, ...rest }) => {
  const resolvedHref = typeof href === "string" ? href : to || "#"
  return <NextLink href={resolvedHref} {...rest} />
}

export const NavLink: React.FC<NavLinkProps> = ({
  to,
  href,
  className,
  ...rest
}) => {
  const router = useRouter()
  const resolvedHref = typeof href === "string" ? href : to || "#"
  const currentPath = router.asPath.split("?")[0]
  const targetPath = resolvedHref.split("?")[0]
  const isActive = currentPath === targetPath
  const resolvedClassName =
    typeof className === "function" ? className({ isActive }) : className

  return (
    <NextLink
      href={resolvedHref}
      className={resolvedClassName}
      {...rest}
    />
  )
}

export const useNavigate = () => {
  const router = useRouter()
  return (to: string | number, options?: NavigateOptions) => {
    if (typeof to === "number") {
      if (to < 0) {
        router.back()
      }
      return
    }
    if (options?.replace) {
      void router.replace(to)
    } else {
      void router.push(to)
    }
  }
}

export const useLocation = () => {
  const router = useRouter()
  const search =
    typeof window === "undefined" ? "" : window.location.search || ""
  const hash = typeof window === "undefined" ? "" : window.location.hash || ""
  const pathname = router.asPath.split("?")[0].split("#")[0] || router.pathname
  return React.useMemo(
    () => ({
      pathname,
      search,
      hash,
      state: null,
      key: router.asPath
    }),
    [pathname, router.asPath, search, hash]
  )
}

export const useSearchParams = (): [
  URLSearchParams,
  (next: URLSearchParams | Record<string, string>, options?: NavigateOptions) => void
] => {
  const router = useRouter()
  const params = React.useMemo(() => {
    const queryString = router.asPath.split("?")[1] || ""
    return new URLSearchParams(queryString)
  }, [router.asPath])

  const setSearchParams = React.useCallback(
    (
      next: URLSearchParams | Record<string, string>,
      options?: NavigateOptions
    ) => {
      const nextParams =
        next instanceof URLSearchParams ? next : new URLSearchParams(next)
      const queryString = nextParams.toString()
      const nextPath = queryString
        ? `${router.pathname}?${queryString}`
        : router.pathname
      if (options?.replace) {
        void router.replace(nextPath)
      } else {
        void router.push(nextPath)
      }
    },
    [router]
  )

  return [params, setSearchParams]
}

export const Routes: React.FC<{ children?: React.ReactNode }> = ({
  children
}) => <>{children}</>

export const Route: React.FC<{ element?: React.ReactNode }> = ({ element }) => (
  <>{element ?? null}</>
)

export const HashRouter: React.FC<{ children?: React.ReactNode }> = ({
  children
}) => <>{children}</>

export const MemoryRouter: React.FC<{ children?: React.ReactNode }> = ({
  children
}) => <>{children}</>
