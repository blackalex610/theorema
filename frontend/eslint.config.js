import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist', 'playwright-report', 'test-results']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    rules: {
      // A leading underscore marks a binding as deliberately unused (e.g.
      // pulling react-markdown's `node` prop off before spreading the rest
      // onto a DOM element).
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_', ignoreRestSiblings: true },
      ],
      // Fast refresh wants component-only modules. These are the deliberate
      // exceptions: each context's hook lives beside its provider, and each
      // ui/ component beside its variants — splitting them buys nothing but
      // an import. Anything not listed here is still flagged.
      'react-refresh/only-export-components': [
        'error',
        {
          allowConstantExport: true,
          allowExportNames: [
            // context hooks
            'useAuth', 'useConnect', 'useDeveloperMode', 'useIsDevMode', 'useSettings', 'useXp',
            // component variants and helpers exported beside their component
            'badgeVariants', 'buttonVariants', 'cardVariants', 'tabsListVariants',
            'riseVariants', 'shellClass', 'useSpringHover', 'practiceIcon',
            'scrollToSection', 'renderNvoDiagram', 'renderMathText', 'installBugReportErrorCapture',
            'normalizeDifficulty', 'DIFFICULTY_XP', 'DIFFICULTY_BADGE',
          ],
        },
      ],
    },
  },
])
