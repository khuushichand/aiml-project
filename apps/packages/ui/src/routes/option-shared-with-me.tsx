import OptionLayout from "~/components/Layouts/Layout"
import { SharedWithMe } from "@/components/Option/SharedWithMe"

const OptionSharedWithMe = () => {
  return (
    <OptionLayout>
      <div className="w-full">
        <SharedWithMe />
      </div>
    </OptionLayout>
  )
}

export default OptionSharedWithMe
