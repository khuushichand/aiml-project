export const updatePageTitle = (title: string = 'tldw Assistant') => {
  if (typeof document === "undefined") return
  document.title = title
}
