import dynamic from "next/dynamic"

export default dynamic(() => import("@/routes/option-sources-detail"), { ssr: false })
