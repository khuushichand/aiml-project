export type DeploymentMode = "self_host"

export const getDeploymentMode = (): DeploymentMode => {
  return "self_host"
}

export const isHostedSaaSMode = (): boolean =>
  false
