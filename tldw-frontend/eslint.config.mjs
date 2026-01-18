import js from "@eslint/js"
import globals from "globals"
import nextPlugin from "@next/eslint-plugin-next"
import reactHooks from "eslint-plugin-react-hooks"
import tsPlugin from "@typescript-eslint/eslint-plugin"
import tsParser from "@typescript-eslint/parser"

const stripConfigs = (plugin) => {
  const { configs, ...rest } = plugin
  return rest
}

const nextRules = nextPlugin.configs["core-web-vitals"]?.rules ?? {}
const reactHooksRules = reactHooks.configs.recommended?.rules ?? {}
const tsRules = tsPlugin.configs.recommended?.rules ?? {}

export default [
  {
    ignores: [
      ".next/**",
      "node_modules/**",
      "components/**",
      "hooks/**",
      "lib/**",
      "models/**",
      "styles/**",
      "types/**",
      "test/**",
      "__tests__/**"
    ]
  },
  js.configs.recommended,
  {
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
      "react-hooks": stripConfigs(reactHooks),
      "@typescript-eslint": stripConfigs(tsPlugin)
    },
    rules: {
      ...tsRules,
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
      "@typescript-eslint/triple-slash-reference": "off",
      "react-hooks/purity": "off",
      "react-hooks/set-state-in-effect": "off",
      "react-hooks/static-components": "off",
      "react-hooks/use-memo": "off",
      "react-hooks/component-hook-factories": "off",
      "react-hooks/preserve-manual-memoization": "off",
      "react-hooks/incompatible-library": "off",
      "react-hooks/immutability": "off",
      "react-hooks/globals": "off",
      "react-hooks/refs": "off",
      "react-hooks/error-boundaries": "off",
      "react-hooks/set-state-in-render": "off",
      "react-hooks/unsupported-syntax": "off",
      "react-hooks/config": "off"
    }
  }
]
