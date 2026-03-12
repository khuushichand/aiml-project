import dynamic from "next/dynamic"

export default dynamic(() => import("@/routes/option-chat-workflows"), {
  ssr: false
})
