import dynamic from "next/dynamic"

export default dynamic(() => import("@/routes/option-shared-with-me"), {
  ssr: false
})
