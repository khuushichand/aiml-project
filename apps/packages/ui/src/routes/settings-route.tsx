import { lazy, type ComponentType, type ReactNode } from "react"
import OptionLayout from "~/components/Layouts/Layout"
import { SettingsLayout } from "~/components/Layouts/SettingsOptionLayout"
import { RouteErrorBoundary } from "@/components/Common/RouteErrorBoundary"

type SettingsRouteProps = {
  children: ReactNode
}

export const SettingsRoute = ({ children }: SettingsRouteProps) => (
  <OptionLayout hideHeader>
    <RouteErrorBoundary routeId="settings" routeLabel="Settings">
      <SettingsLayout>{children}</SettingsLayout>
    </RouteErrorBoundary>
  </OptionLayout>
)

type SettingsModule = {
  default?: ComponentType
  [key: string]: ComponentType | undefined
}

export function createSettingsRoute(
  loader: () => Promise<SettingsModule>,
  exportName: string = "default"
) {
  return lazy(async () => {
    const module = await loader()
    const Page =
      exportName === "default" ? module.default : module[exportName]

    if (!Page) {
      throw new Error(`Settings route missing export: ${exportName}`)
    }

    const Wrapped = () => (
      <SettingsRoute>
        <Page />
      </SettingsRoute>
    )

    return { default: Wrapped }
  })
}
