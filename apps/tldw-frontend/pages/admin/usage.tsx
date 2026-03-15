import dynamic from "next/dynamic"

export default dynamic(() => import("@/routes/option-admin-usage"), { ssr: false })
