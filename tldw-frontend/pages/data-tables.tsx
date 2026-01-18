import dynamic from "next/dynamic"

export default dynamic(() => import("@/routes/option-data-tables"), { ssr: false })
