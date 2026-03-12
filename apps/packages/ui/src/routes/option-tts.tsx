import OptionLayout from "~/components/Layouts/Layout"
import SpeechPlaygroundPage from "@/components/Option/Speech/SpeechPlaygroundPage"
import { RouteErrorBoundary } from "@/components/Common/RouteErrorBoundary"

const OptionTts = () => {
  return (
    <RouteErrorBoundary routeId="tts" routeLabel="TTS Playground">
      <OptionLayout>
        <SpeechPlaygroundPage lockedMode="listen" hideModeSwitcher />
      </OptionLayout>
    </RouteErrorBoundary>
  )
}

export default OptionTts
