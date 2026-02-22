import dynamic from "next/dynamic"

export default dynamic(() => import("@/routes/sidepanel-persona"), { ssr: false })
