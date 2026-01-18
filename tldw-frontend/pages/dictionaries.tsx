import dynamic from "next/dynamic"

export default dynamic(() => import("@/routes/option-dictionaries"), { ssr: false })
