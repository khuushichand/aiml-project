import dynamic from "next/dynamic"

export default dynamic(async () => {
  const { useRouter } = await import("next/router")
  const { useEffect } = await import("react")
  const Page = () => {
    const router = useRouter()
    useEffect(() => {
      void router.replace("/knowledge")
    }, [router])
    return null
  }
  return { default: Page }
}, { ssr: false })
