import { ChatDocuments } from "@/models/ChatTypes"
import { isAmazonURL, parseAmazonWebsite } from "@/parser/amazon"
import { defaultExtractContent } from "@/parser/default"
import { isTwitterProfile, isTwitterTimeline, parseTweetProfile, parseTwitterTimeline } from "@/parser/twitter"
import { isWikipedia, parseWikipedia } from "@/parser/wiki"
import { getMaxContextSize } from "@/services/kb"

const formatDocumentHeader = (title: string, url: string) => {
    const hostname = new URL(url).hostname
    return `# ${title} (${hostname}) \n\n`
}

const truncateContent = (content: string, maxLength: number): string => {
    if (content.length <= maxLength) {
        return content
    }

    // Try to truncate at word boundary
    const truncated = content.substring(0, maxLength)
    const lastSpaceIndex = truncated.lastIndexOf(' ')

    if (lastSpaceIndex > maxLength * 0.8) {
        return truncated.substring(0, lastSpaceIndex) + '...'
    }

    return truncated + '...'
}

export const getTabContents = async (documents: ChatDocuments) => {
    const result: string[] = []
    const maxContextSize = await getMaxContextSize()

    // Calculate available space per document
    const contextPerDocument = Math.floor(maxContextSize / documents.length)
    let remainingContext = maxContextSize

    for (const doc of documents) {
        try {
            if (remainingContext <= 0) break

            const pageContent = await browser.scripting.executeScript({
                target: { tabId: doc.tabId! },
                func: () => ({
                    html: document.documentElement.outerHTML,
                    title: document.title,
                    url: window.location.href,
                    isPDF: document.contentType === 'application/pdf'
                })
            })
            const content = pageContent[0].result as {
                html: string
                title: string
                url: string
                isPDF: boolean
            }
            const docUrl = doc.url ?? ""
            const header = formatDocumentHeader(doc.title ?? "", docUrl)
            let extractedContent = ""

            if (isWikipedia(docUrl)) {
                extractedContent = parseWikipedia(content.html)
            } else if (isAmazonURL(docUrl)) {
                extractedContent = parseAmazonWebsite(content.html)
            } else if (isTwitterProfile(docUrl)) {
                extractedContent = parseTweetProfile(content.html)
            } else if (isTwitterTimeline(docUrl)) {
                extractedContent = parseTwitterTimeline(content.html)
            } else {
                extractedContent = defaultExtractContent(content.html)
            }

            // Calculate available space for this document's content
            const headerLength = header.length
            const availableSpace = Math.min(
                contextPerDocument - headerLength,
                remainingContext - headerLength
            )

            if (availableSpace > 0) {
                const truncatedContent = truncateContent(extractedContent, availableSpace)
                const documentContent = `${header}${truncatedContent}`

                result.push(documentContent)
                remainingContext -= documentContent.length
            }
        } catch (e) {
            console.error("Error processing document:", e)
            continue
        }
    }

    return result.join("\n\n")
}
