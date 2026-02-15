import dynamic from "next/dynamic"

export default dynamic(() => import("@/routes/option-audiobook-studio"), { ssr: false })
