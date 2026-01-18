import dynamic from "next/dynamic"

export default dynamic(() => import("@/routes/sidepanel-error-boundary-test"), { ssr: false })
