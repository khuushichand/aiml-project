import React from "react"
import { PublicShare } from "@/components/Option/PublicShare"

interface PublicShareRouteProps {
  token: string
}

const OptionPublicShare: React.FC<PublicShareRouteProps> = ({ token }) => {
  return <PublicShare token={token} />
}

export default OptionPublicShare
