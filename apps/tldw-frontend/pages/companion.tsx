import dynamic from "next/dynamic"
import RouteChunkLoading from "@web/components/navigation/RouteChunkLoading"

export default dynamic(() => import("@/routes/option-companion"), {
  ssr: false,
  loading: () => (
    <RouteChunkLoading
      eyebrow="Companion Home"
      title="Loading Companion"
      description="Preparing your companion dashboard."
      testId="companion-route-loading"
    />
  )
})
