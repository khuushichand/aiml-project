import dynamic from "next/dynamic"

export default dynamic(() => import("@/routes/option-repo2txt"), { ssr: false })
