import { useEffect } from "react"
import { runStorageMigrations } from "@/utils/storage-migrations"

export const useStorageMigrations = () => {
  useEffect(() => {
    void runStorageMigrations()
  }, [])
}
