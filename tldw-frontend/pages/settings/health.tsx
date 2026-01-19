import dynamic from "next/dynamic"

export default dynamic(() => import("@/routes/option-settings-health"), { ssr: false })
