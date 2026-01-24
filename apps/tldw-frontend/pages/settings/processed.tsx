import dynamic from "next/dynamic"

export default dynamic(() => import("@/routes/option-settings-processed"), { ssr: false })
