import OptionLayout from "~/components/Layouts/Layout"
import { WritingPlayground } from "@/components/Option/WritingPlayground"

const OptionWritingPlayground = () => {
  return (
    <OptionLayout>
      <div className="w-full h-[calc(100vh-64px)] overflow-hidden">
        <WritingPlayground />
      </div>
    </OptionLayout>
  )
}

export default OptionWritingPlayground
