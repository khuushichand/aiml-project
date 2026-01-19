import dynamic from "next/dynamic"

export default dynamic(() => import("@/routes/option-prompt-studio"), { ssr: false })
