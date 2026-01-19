import dynamic from "next/dynamic"

export default dynamic(() => import("@/routes/sidepanel-agent"), { ssr: false })
