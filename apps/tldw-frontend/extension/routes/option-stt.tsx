import OptionLayout from "@web/extension/components/Layouts/Layout"
import SpeechPlaygroundPage from "@/components/Option/Speech/SpeechPlaygroundPage"

const OptionStt = () => {
  return (
    <OptionLayout>
      <SpeechPlaygroundPage initialMode="speak" />
    </OptionLayout>
  )
}

export default OptionStt
