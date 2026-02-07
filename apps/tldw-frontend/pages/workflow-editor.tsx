import dynamic from "next/dynamic"

export default dynamic(() => import("@/routes/option-workflow-editor"), { ssr: false })
