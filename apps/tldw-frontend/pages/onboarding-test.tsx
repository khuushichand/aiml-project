import dynamic from "next/dynamic"

export default dynamic(() => import("@/routes/option-onboarding-test"), { ssr: false })
