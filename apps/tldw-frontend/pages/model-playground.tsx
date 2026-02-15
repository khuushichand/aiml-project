import dynamic from "next/dynamic"

export default dynamic(() => import("@/routes/option-model-playground"), { ssr: false })
