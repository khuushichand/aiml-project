import dynamic from "next/dynamic"

export default dynamic(() => import("@/routes/option-evaluations"), { ssr: false })
