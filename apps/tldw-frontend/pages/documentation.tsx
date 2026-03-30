import dynamic from "next/dynamic"

export default dynamic(() => import("@web/components/documentation/WebDocumentationRoute"), {
  ssr: false
})
