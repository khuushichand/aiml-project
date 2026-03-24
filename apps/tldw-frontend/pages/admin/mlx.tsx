import dynamic from "next/dynamic"
import RouteChunkLoading from "@web/components/navigation/RouteChunkLoading"

export default dynamic(() => import("@/routes/option-admin-mlx"), {
  ssr: false,
  loading: () => (
    <RouteChunkLoading
      eyebrow="Admin"
      title="Loading MLX Admin"
      description="Preparing MLX model controls and status."
      testId="admin-mlx-route-loading"
    />
  )
})
