export type DeploymentMode = "self_host" | "hosted"

export const getDeploymentMode = (): DeploymentMode => {
  const raw = String(
    process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE || ""
  ).trim().toLowerCase()

  return raw === "hosted" ? "hosted" : "self_host"
}

export const isHostedSaaSMode = (): boolean =>
  getDeploymentMode() === "hosted"
