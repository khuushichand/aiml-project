import dynamic from "next/dynamic"

export default dynamic(() => import("@/routes/option-media"), { ssr: false })
