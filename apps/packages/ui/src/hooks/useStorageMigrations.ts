import { useEffect } from "react"
import { runStorageMigrations } from "@/utils/storage-migrations"

export const useStorageMigrations = (enabled = true) => {
  useEffect(() => {
    if (!enabled) return
    void runStorageMigrations()
  }, [enabled])
}
