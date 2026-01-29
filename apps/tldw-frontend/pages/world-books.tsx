import dynamic from "next/dynamic"

export default dynamic(() => import("@/routes/option-world-books"), { ssr: false })
