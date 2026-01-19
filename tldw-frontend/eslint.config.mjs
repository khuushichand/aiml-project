import js from "@eslint/js"
import globals from "globals"
import nextPlugin from "@next/eslint-plugin-next"
import react from "eslint-plugin-react"
import reactHooks from "eslint-plugin-react-hooks"
import tsPlugin from "@typescript-eslint/eslint-plugin"
import tsParser from "@typescript-eslint/parser"

const stripConfigs = (plugin) => {
  const { configs, ...rest } = plugin
  return rest
}

const nextRules = nextPlugin.configs["core-web-vitals"]?.rules ?? {}
const reactHooksRules = reactHooks.configs.recommended?.rules ?? {}
const reactRules = react.configs.recommended?.rules ?? {}
const tsRules = tsPlugin.configs.recommended?.rules ?? {}
const codeFiles = ["**/*.{js,jsx,ts,tsx,mjs,cjs}"]
const cjsFiles = ["**/*.cjs"]

export default [
  {
    ignores: [
      ".next/**",
      "node_modules/**"
    ]
  },
  {
    ...js.configs.recommended,
    files: codeFiles
  },
  {
    files: codeFiles,
    languageOptions: {
      parser: tsParser,
      parserOptions: {
        ecmaVersion: "latest",
        sourceType: "module",
        ecmaFeatures: { jsx: true }
      },
      globals: {
        ...globals.browser,
        ...globals.node,
        React: "readonly",
        NodeJS: "readonly",
        fetch: "readonly",
        process: "readonly"
      }
    },
    plugins: {
      "@next/next": stripConfigs(nextPlugin),
      "react": stripConfigs(react),
      "react-hooks": stripConfigs(reactHooks),
      "@typescript-eslint": stripConfigs(tsPlugin)
    },
    settings: {
      react: { version: "detect" }
    },
    rules: {
      ...tsRules,
      ...reactRules,
      ...reactHooksRules,
      ...nextRules,
      "@typescript-eslint/no-explicit-any": "warn",
      "@typescript-eslint/no-unused-vars": [
        "warn",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" }
      ],
      "no-unused-vars": "off",
      "no-empty": ["error", { allowEmptyCatch: true }],
      "no-useless-catch": "warn",
      "@typescript-eslint/triple-slash-reference": "off"
    }
  },
  {
    files: cjsFiles,
    languageOptions: {
      parserOptions: { sourceType: "script" }
    }
  }
]
