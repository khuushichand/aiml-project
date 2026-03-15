import dynamic from "next/dynamic"

export default dynamic(() => import("@/routes/option-presentation-studio"), { ssr: false })
