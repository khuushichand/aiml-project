import OptionLayout from "@web/extension/components/Layouts/Layout"
import SpeechPlaygroundPage from "@/components/Option/Speech/SpeechPlaygroundPage"

const OptionTts = () => {
  return (
    <OptionLayout>
      <SpeechPlaygroundPage initialMode="listen" />
    </OptionLayout>
  )
}

export default OptionTts
