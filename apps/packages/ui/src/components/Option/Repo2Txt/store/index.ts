import { createStore } from "zustand/vanilla"
import { createFileTreeSlice } from "./fileTreeSlice"
import type { Repo2TxtStoreState } from "./types"

export const createRepo2TxtStore = () =>
  createStore<Repo2TxtStoreState>()((...args) => ({
    ...createFileTreeSlice(...args)
  }))
