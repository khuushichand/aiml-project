import dynamic from "next/dynamic"

export default dynamic(() => import("@/routes/option-acp-playground"), { ssr: false })
