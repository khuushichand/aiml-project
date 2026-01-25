import { lazy, type ComponentType, type ReactNode } from "react"
import OptionLayout from "@web/extension/components/Layouts/Layout"
import { SettingsLayout } from "~/components/Layouts/SettingsOptionLayout"

type SettingsRouteProps = {
  children: ReactNode
}

export const SettingsRoute = ({ children }: SettingsRouteProps) => (
  <OptionLayout hideHeader>
    <SettingsLayout>{children}</SettingsLayout>
  </OptionLayout>
)

type SettingsModule = {
  default?: ComponentType
  [key: string]: ComponentType | undefined
}

export const createSettingsRoute = (
  loader: () => Promise<SettingsModule>,
  exportName: string = "default"
) =>
  lazy(async () => {
    const loadedModule = await loader()
    const Page =
      exportName === "default" ? loadedModule.default : loadedModule[exportName]

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
