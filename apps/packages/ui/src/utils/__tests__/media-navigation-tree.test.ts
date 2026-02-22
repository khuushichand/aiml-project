import { describe, expect, it } from 'vitest'

import type { MediaNavigationNode } from '@/hooks/useMediaNavigation'
import {
  buildMediaNavigationTreeIndex,
  findQuickJumpMatches
} from '@/utils/media-navigation-tree'

const makeNode = (overrides: Partial<MediaNavigationNode>): MediaNavigationNode => ({
  id: overrides.id || 'node',
  parent_id: overrides.parent_id ?? null,
  level: overrides.level ?? 0,
  title: overrides.title || 'Untitled',
  order: overrides.order ?? 0,
  path_label: overrides.path_label ?? null,
  target_type: overrides.target_type || 'char_range',
  target_start: overrides.target_start ?? 0,
  target_end: overrides.target_end ?? 10,
  target_href: overrides.target_href ?? null,
  source: overrides.source || 'test',
  confidence: overrides.confidence ?? null
})

describe('media-navigation-tree', () => {
  it('indexes roots and children with stable sorting', () => {
    const nodes: MediaNavigationNode[] = [
      makeNode({ id: 'root-b', title: 'B', order: 2 }),
      makeNode({ id: 'root-a', title: 'A', order: 1 }),
      makeNode({ id: 'child-a-2', parent_id: 'root-a', level: 1, order: 2 }),
      makeNode({ id: 'child-a-1', parent_id: 'root-a', level: 1, order: 1 }),
      makeNode({ id: 'orphan', parent_id: 'missing-parent', order: 0 })
    ]

    const index = buildMediaNavigationTreeIndex(nodes)
    expect(index.roots.map((n) => n.id)).toEqual(['orphan', 'root-a', 'root-b'])
    expect(index.childrenByParent['root-a'].map((n) => n.id)).toEqual([
      'child-a-1',
      'child-a-2'
    ])
  })

  it('prioritizes exact path-label quick jump matches', () => {
    const nodes: MediaNavigationNode[] = [
      makeNode({ id: 'n-1', title: 'Section 12.5 overview', path_label: null }),
      makeNode({ id: 'n-2', title: 'References', path_label: '12.5' }),
      makeNode({ id: 'n-3', title: 'Deep dive', path_label: '12.50' })
    ]

    const matches = findQuickJumpMatches(nodes, '12.5')
    expect(matches.map((n) => n.id)).toEqual(['n-2'])
  })

  it('falls back to prefix path-label matches, then title matches', () => {
    const nodes: MediaNavigationNode[] = [
      makeNode({ id: 'n-1', title: 'Introduction', path_label: '1' }),
      makeNode({ id: 'n-2', title: 'Chapter Twelve', path_label: '12.1', order: 2 }),
      makeNode({ id: 'n-3', title: 'Chapter Twelve Advanced', path_label: '12.5', order: 1 }),
      makeNode({ id: 'n-4', title: 'Intro Appendix', path_label: null, order: 3 })
    ]

    expect(findQuickJumpMatches(nodes, '12').map((n) => n.id)).toEqual([
      'n-3',
      'n-2'
    ])
    expect(findQuickJumpMatches(nodes, 'intro').map((n) => n.id)).toEqual([
      'n-1',
      'n-4'
    ])
  })
})
