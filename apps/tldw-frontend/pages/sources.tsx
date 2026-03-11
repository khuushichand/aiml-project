import dynamic from "next/dynamic"

export default dynamic(() => import("@/routes/option-sources"), { ssr: false })
