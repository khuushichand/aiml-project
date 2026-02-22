import dynamic from "next/dynamic"

export default dynamic(() => import("@/routes/option-skills"), { ssr: false })
