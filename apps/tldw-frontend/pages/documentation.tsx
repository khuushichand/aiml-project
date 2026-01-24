import dynamic from "next/dynamic"

export default dynamic(() => import("@/routes/option-documentation"), { ssr: false })
