import dynamic from "next/dynamic"

export default dynamic(() => import("@/routes/sidepanel-chat"), {
  ssr: false
})

