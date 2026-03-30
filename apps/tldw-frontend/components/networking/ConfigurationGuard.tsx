import React from "react"
import {
  detectNetworkingIssue,
  type DeploymentEnv
} from "@web/lib/api-base"
import { ConfigurationErrorScreen } from "./ConfigurationErrorScreen"

type ConfigurationGuardProps = {
  children: React.ReactNode
}

const getDeploymentEnv = (): DeploymentEnv => ({
  NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE: process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE,
  NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL
})

const getCurrentIssue = () => {
  if (typeof window === "undefined") {
    return undefined
  }

  return detectNetworkingIssue(getDeploymentEnv(), window.location.origin)
}

export const ConfigurationGuard = ({ children }: ConfigurationGuardProps) => {
  const [issue, setIssue] = React.useState<ReturnType<typeof getCurrentIssue>>()
  const [hasResolved, setHasResolved] = React.useState(false)

  React.useEffect(() => {
    setIssue(getCurrentIssue())
    setHasResolved(true)
  }, [])

  if (!hasResolved) {
    return null
  }

  if (issue) {
    return <ConfigurationErrorScreen issue={issue} />
  }

  return <>{children}</>
}
