import dynamic from "next/dynamic"
import { useRouter } from "next/router"

const PublicShareContent = dynamic(
  () => import("@/components/Option/PublicShare"),
  { ssr: false }
)

export default function PublicSharePage() {
  const router = useRouter()
  const { token } = router.query

  if (!token || typeof token !== "string") {
    return null
  }

  return <PublicShareContent token={token} />
}
