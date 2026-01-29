import dynamic from "next/dynamic"

export default dynamic(() => import("@/routes/option-setup"), { ssr: false })
