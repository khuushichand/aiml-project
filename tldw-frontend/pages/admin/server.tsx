import dynamic from "next/dynamic"

export default dynamic(() => import("@/routes/option-admin-server"), { ssr: false })
