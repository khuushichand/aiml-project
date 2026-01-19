import dynamic from "next/dynamic"

export default dynamic(() => import("@/routes/option-quick-chat-popout"), { ssr: false })
