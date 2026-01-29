import OptionLayout from "@web/components/layout/WebLayout"
import SpeechPlaygroundPage from "@/components/Option/Speech/SpeechPlaygroundPage"

const OptionTts = () => {
  return (
    <OptionLayout>
      <SpeechPlaygroundPage initialMode="listen" />
    </OptionLayout>
  )
}

export default OptionTts
