import { useState } from "react"
import { Button, Empty, Input, List, Spin, Tag, Typography } from "antd"
import { Search, BookOpen, Plus } from "lucide-react"
import { useWritingPlaygroundStore } from "@/store/writing-playground"
import {
  createManuscriptCitation,
  searchManuscriptResearch,
  type ManuscriptResearchResponse,
  type ManuscriptResearchResult,
} from "@/services/writing-playground"

type ResearchTabProps = { isOnline: boolean }

export function ResearchTab({ isOnline }: ResearchTabProps) {
  const { activeNodeId } = useWritingPlaygroundStore()
  const [query, setQuery] = useState("")
  const [results, setResults] = useState<ManuscriptResearchResult[]>([])
  const [searching, setSearching] = useState(false)
  const [citedIds, setCitedIds] = useState<Set<string>>(new Set())

  const handleSearch = async () => {
    if (!query.trim() || !activeNodeId) return
    setSearching(true)
    try {
      const resp: ManuscriptResearchResponse = await searchManuscriptResearch(activeNodeId, query.trim())
      setResults(resp.results || [])
    } catch {
      setResults([])
    } finally {
      setSearching(false)
    }
  }

  const handleCite = async (result: ManuscriptResearchResult) => {
    if (!activeNodeId) return
    try {
      await createManuscriptCitation(activeNodeId, {
        source_type: result.source_type || "research",
        source_title: result.title || result.source_title || "Untitled",
        excerpt: result.snippet || result.excerpt || "",
        query_used: query,
      })
      setCitedIds((prev) => new Set(prev).add(result.id || result.title))
    } catch {
      // silently fail
    }
  }

  if (!activeNodeId) {
    return (
      <Empty
        image={<BookOpen className="mx-auto h-8 w-8 text-gray-300" />}
        description="Select a scene to search your knowledge base"
        className="py-8"
      />
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex gap-1">
        <Input
          size="small"
          placeholder="Search your knowledge base..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onPressEnter={handleSearch}
          prefix={<Search className="h-3 w-3 text-gray-400" />}
        />
        <Button
          size="small"
          type="primary"
          loading={searching}
          disabled={!query.trim() || !isOnline}
          onClick={handleSearch}
        >
          Search
        </Button>
      </div>

      {searching ? (
        <div className="flex justify-center py-4"><Spin size="small" /></div>
      ) : results.length > 0 ? (
        <List
          size="small"
          dataSource={results}
          renderItem={(result: ManuscriptResearchResult, index: number) => {
            const key = result.id || result.title || String(index)
            const isCited = citedIds.has(key)
            return (
              <List.Item className="!px-0 !py-2" actions={[
                <Button
                  key="cite"
                  size="small"
                  type={isCited ? "default" : "primary"}
                  icon={<Plus className="h-3 w-3" />}
                  disabled={isCited}
                  onClick={() => handleCite({ ...result, id: key })}
                >
                  {isCited ? "Cited" : "Cite"}
                </Button>
              ]}>
                <List.Item.Meta
                  title={<Typography.Text className="text-sm">{result.title || result.source_title || "Untitled"}</Typography.Text>}
                  description={
                    <Typography.Text type="secondary" className="text-xs">
                      {result.snippet || result.excerpt || ""}
                    </Typography.Text>
                  }
                />
              </List.Item>
            )
          }}
        />
      ) : query.trim() ? (
        <Empty description="No results found" className="py-4" />
      ) : null}
    </div>
  )
}

export default ResearchTab
