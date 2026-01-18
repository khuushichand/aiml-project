import dynamic from "next/dynamic"

export default dynamic(() => import("@/routes/option-media-multi"), { ssr: false })
