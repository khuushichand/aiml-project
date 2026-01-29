import OptionLayout from "@web/components/layout/WebLayout"
import SpeechPlaygroundPage from "@/components/Option/Speech/SpeechPlaygroundPage"

const OptionStt = () => {
  return (
    <OptionLayout>
      <SpeechPlaygroundPage initialMode="speak" />
    </OptionLayout>
  )
}

export default OptionStt
