import OptionLayout from "~/components/Layouts/Layout"
import { WritingPlayground } from "@/components/Option/WritingPlayground"

const OptionWritingPlayground = () => {
  return (
    <OptionLayout>
      <div
        data-testid="writing-playground-route-shell"
        className="flex min-h-0 flex-1 overflow-hidden">
        <WritingPlayground />
      </div>
    </OptionLayout>
  )
}

export default OptionWritingPlayground
