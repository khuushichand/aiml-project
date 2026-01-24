import { useStorage } from "@plasmohq/storage/hook"
import { DEFAULT_CHAT_SETTINGS } from "@/types/chat-settings"

export const useChatSettings = () => {
  const [copilotResumeLastChat, setCopilotResumeLastChat] = useStorage(
    "copilotResumeLastChat",
    DEFAULT_CHAT_SETTINGS.copilotResumeLastChat
  )
  const [defaultChatWithWebsite, setDefaultChatWithWebsite] = useStorage(
    "defaultChatWithWebsite",
    DEFAULT_CHAT_SETTINGS.defaultChatWithWebsite
  )
  const [webUIResumeLastChat, setWebUIResumeLastChat] = useStorage(
    "webUIResumeLastChat",
    DEFAULT_CHAT_SETTINGS.webUIResumeLastChat
  )
  const [hideCurrentChatModelSettings, setHideCurrentChatModelSettings] =
    useStorage(
      "hideCurrentChatModelSettings",
      DEFAULT_CHAT_SETTINGS.hideCurrentChatModelSettings
    )
  const [hideQuickChatHelper, setHideQuickChatHelper] = useStorage(
    "hideQuickChatHelper",
    DEFAULT_CHAT_SETTINGS.hideQuickChatHelper
  )
  const [restoreLastChatModel, setRestoreLastChatModel] = useStorage(
    "restoreLastChatModel",
    DEFAULT_CHAT_SETTINGS.restoreLastChatModel
  )
  const [generateTitle, setGenerateTitle] = useStorage(
    "titleGenEnabled",
    DEFAULT_CHAT_SETTINGS.titleGenEnabled
  )
  const [checkWideMode, setCheckWideMode] = useStorage(
    "checkWideMode",
    DEFAULT_CHAT_SETTINGS.checkWideMode
  )
  const [stickyChatInput, setStickyChatInput] = useStorage(
    "stickyChatInput",
    DEFAULT_CHAT_SETTINGS.stickyChatInput
  )
  const [menuDensity, setMenuDensity] = useStorage(
    "menuDensity",
    DEFAULT_CHAT_SETTINGS.menuDensity
  )
  const [openReasoning, setOpenReasoning] = useStorage(
    "openReasoning",
    DEFAULT_CHAT_SETTINGS.openReasoning
  )
  const [userChatBubble, setUserChatBubble] = useStorage(
    "userChatBubble",
    DEFAULT_CHAT_SETTINGS.userChatBubble
  )
  const [autoCopyResponseToClipboard, setAutoCopyResponseToClipboard] =
    useStorage(
      "autoCopyResponseToClipboard",
      DEFAULT_CHAT_SETTINGS.autoCopyResponseToClipboard
    )
  const [useMarkdownForUserMessage, setUseMarkdownForUserMessage] = useStorage(
    "useMarkdownForUserMessage",
    DEFAULT_CHAT_SETTINGS.useMarkdownForUserMessage
  )
  const [copyAsFormattedText, setCopyAsFormattedText] = useStorage(
    "copyAsFormattedText",
    DEFAULT_CHAT_SETTINGS.copyAsFormattedText
  )
  const [allowExternalImages, setAllowExternalImages] = useStorage(
    "allowExternalImages",
    DEFAULT_CHAT_SETTINGS.allowExternalImages
  )
  const [tabMentionsEnabled, setTabMentionsEnabled] = useStorage(
    "tabMentionsEnabled",
    DEFAULT_CHAT_SETTINGS.tabMentionsEnabled
  )
  const [pasteLargeTextAsFile, setPasteLargeTextAsFile] = useStorage(
    "pasteLargeTextAsFile",
    DEFAULT_CHAT_SETTINGS.pasteLargeTextAsFile
  )
  const [sidepanelTemporaryChat, setSidepanelTemporaryChat] = useStorage(
    "sidepanelTemporaryChat",
    DEFAULT_CHAT_SETTINGS.sidepanelTemporaryChat
  )
  const [removeReasoningTagFromCopy, setRemoveReasoningTagFromCopy] =
    useStorage(
      "removeReasoningTagFromCopy",
      DEFAULT_CHAT_SETTINGS.removeReasoningTagFromCopy
    )
  const [promptSearchIncludeServer, setPromptSearchIncludeServer] =
    useStorage(
      "promptSearchIncludeServer",
      DEFAULT_CHAT_SETTINGS.promptSearchIncludeServer
    )
  const [userTextColor, setUserTextColor] = useStorage(
    "chatUserTextColor",
    DEFAULT_CHAT_SETTINGS.chatUserTextColor
  )
  const [assistantTextColor, setAssistantTextColor] = useStorage(
    "chatAssistantTextColor",
    DEFAULT_CHAT_SETTINGS.chatAssistantTextColor
  )
  const [userTextFont, setUserTextFont] = useStorage(
    "chatUserTextFont",
    DEFAULT_CHAT_SETTINGS.chatUserTextFont
  )
  const [assistantTextFont, setAssistantTextFont] = useStorage(
    "chatAssistantTextFont",
    DEFAULT_CHAT_SETTINGS.chatAssistantTextFont
  )
  const [userTextSize, setUserTextSize] = useStorage(
    "chatUserTextSize",
    DEFAULT_CHAT_SETTINGS.chatUserTextSize
  )
  const [assistantTextSize, setAssistantTextSize] = useStorage(
    "chatAssistantTextSize",
    DEFAULT_CHAT_SETTINGS.chatAssistantTextSize
  )

  return {
    copilotResumeLastChat:
      copilotResumeLastChat ?? DEFAULT_CHAT_SETTINGS.copilotResumeLastChat,
    setCopilotResumeLastChat,
    defaultChatWithWebsite:
      defaultChatWithWebsite ?? DEFAULT_CHAT_SETTINGS.defaultChatWithWebsite,
    setDefaultChatWithWebsite,
    webUIResumeLastChat:
      webUIResumeLastChat ?? DEFAULT_CHAT_SETTINGS.webUIResumeLastChat,
    setWebUIResumeLastChat,
    hideCurrentChatModelSettings:
      hideCurrentChatModelSettings ??
      DEFAULT_CHAT_SETTINGS.hideCurrentChatModelSettings,
    setHideCurrentChatModelSettings,
    hideQuickChatHelper:
      hideQuickChatHelper ?? DEFAULT_CHAT_SETTINGS.hideQuickChatHelper,
    setHideQuickChatHelper,
    restoreLastChatModel:
      restoreLastChatModel ?? DEFAULT_CHAT_SETTINGS.restoreLastChatModel,
    setRestoreLastChatModel,
    generateTitle: generateTitle ?? DEFAULT_CHAT_SETTINGS.titleGenEnabled,
    setGenerateTitle,
    checkWideMode: checkWideMode ?? DEFAULT_CHAT_SETTINGS.checkWideMode,
    setCheckWideMode,
    stickyChatInput:
      stickyChatInput ?? DEFAULT_CHAT_SETTINGS.stickyChatInput,
    setStickyChatInput,
    menuDensity: menuDensity ?? DEFAULT_CHAT_SETTINGS.menuDensity,
    setMenuDensity,
    openReasoning: openReasoning ?? DEFAULT_CHAT_SETTINGS.openReasoning,
    setOpenReasoning,
    userChatBubble: userChatBubble ?? DEFAULT_CHAT_SETTINGS.userChatBubble,
    setUserChatBubble,
    autoCopyResponseToClipboard:
      autoCopyResponseToClipboard ??
      DEFAULT_CHAT_SETTINGS.autoCopyResponseToClipboard,
    setAutoCopyResponseToClipboard,
    useMarkdownForUserMessage:
      useMarkdownForUserMessage ??
      DEFAULT_CHAT_SETTINGS.useMarkdownForUserMessage,
    setUseMarkdownForUserMessage,
    copyAsFormattedText:
      copyAsFormattedText ?? DEFAULT_CHAT_SETTINGS.copyAsFormattedText,
    setCopyAsFormattedText,
    allowExternalImages:
      allowExternalImages ?? DEFAULT_CHAT_SETTINGS.allowExternalImages,
    setAllowExternalImages,
    tabMentionsEnabled:
      tabMentionsEnabled ?? DEFAULT_CHAT_SETTINGS.tabMentionsEnabled,
    setTabMentionsEnabled,
    pasteLargeTextAsFile:
      pasteLargeTextAsFile ?? DEFAULT_CHAT_SETTINGS.pasteLargeTextAsFile,
    setPasteLargeTextAsFile,
    sidepanelTemporaryChat:
      sidepanelTemporaryChat ?? DEFAULT_CHAT_SETTINGS.sidepanelTemporaryChat,
    setSidepanelTemporaryChat,
    removeReasoningTagFromCopy:
      removeReasoningTagFromCopy ??
      DEFAULT_CHAT_SETTINGS.removeReasoningTagFromCopy,
    setRemoveReasoningTagFromCopy,
    promptSearchIncludeServer:
      promptSearchIncludeServer ??
      DEFAULT_CHAT_SETTINGS.promptSearchIncludeServer,
    setPromptSearchIncludeServer,
    userTextColor: userTextColor ?? DEFAULT_CHAT_SETTINGS.chatUserTextColor,
    setUserTextColor,
    assistantTextColor:
      assistantTextColor ?? DEFAULT_CHAT_SETTINGS.chatAssistantTextColor,
    setAssistantTextColor,
    userTextFont: userTextFont ?? DEFAULT_CHAT_SETTINGS.chatUserTextFont,
    setUserTextFont,
    assistantTextFont:
      assistantTextFont ?? DEFAULT_CHAT_SETTINGS.chatAssistantTextFont,
    setAssistantTextFont,
    userTextSize: userTextSize ?? DEFAULT_CHAT_SETTINGS.chatUserTextSize,
    setUserTextSize,
    assistantTextSize:
      assistantTextSize ?? DEFAULT_CHAT_SETTINGS.chatAssistantTextSize,
    setAssistantTextSize
  }
}
