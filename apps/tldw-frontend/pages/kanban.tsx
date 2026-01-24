import dynamic from "next/dynamic"

export default dynamic(() => import("@/routes/option-kanban-playground"), { ssr: false })
