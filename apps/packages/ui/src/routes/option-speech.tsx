import OptionLayout from "~/components/Layouts/Layout"
import SpeechPlaygroundPage from "@/components/Option/Speech/SpeechPlaygroundPage"
import { RouteErrorBoundary } from "@/components/Common/RouteErrorBoundary"

const OptionSpeech = () => {
  return (
    <RouteErrorBoundary routeId="speech" routeLabel="Speech Playground">
      <OptionLayout>
        <SpeechPlaygroundPage />
      </OptionLayout>
    </RouteErrorBoundary>
  )
}

export default OptionSpeech
