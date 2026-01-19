import dynamic from "next/dynamic"

export default dynamic(() => import("@/routes/option-index"), { ssr: false })
