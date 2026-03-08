import OptionLayout from "~/components/Layouts/Layout"
import { WritingPlayground } from "@/components/Option/WritingPlayground"

const OptionWritingPlayground = () => {
  return (
    <OptionLayout>
      {/* 64px = OptionLayout header height */}
      <div className="w-full h-[calc(100vh-64px)] overflow-hidden">
        <WritingPlayground />
      </div>
    </OptionLayout>
  )
}

export default OptionWritingPlayground
