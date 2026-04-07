import { useMemo } from "react"
import { useTheme } from "./useTheme"

/**
 * Maps theme component variant tokens to Ant Design component props.
 * Use this in components that render Ant Design <Input>, <Select>, or <Button>.
 */
export function useAntdVariants() {
  const { themeDefinition } = useTheme()
  const { buttonStyle, inputStyle } = themeDefinition.components

  return useMemo(() => ({
    /** Pass to <Button shape={buttonShape}> */
    buttonShape: buttonStyle === "pill" ? ("round" as const) : ("default" as const),

    /** Pass to <Input variant={inputVariant}> or <Select variant={inputVariant}> */
    inputVariant: (
      inputStyle === "underlined" ? "borderless"
      : inputStyle === "filled" ? "filled"
      : "outlined"
    ) as "borderless" | "filled" | "outlined",
  }), [buttonStyle, inputStyle])
}
