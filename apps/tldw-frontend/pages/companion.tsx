import dynamic from "next/dynamic"

export default dynamic(() => import("@/routes/option-companion"), { ssr: false })
