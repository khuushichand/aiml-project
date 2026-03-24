import dynamic from "next/dynamic"

export default dynamic(() => import("@/routes/option-admin-watchlists-items"), { ssr: false })
