import dynamic from "next/dynamic"

export default dynamic(() => import("@/routes/option-agent-tasks"), { ssr: false })
