import js from '@eslint/js'
import skipFormatting from '@vue/eslint-config-prettier/skip-formatting'
import { defineConfigWithVueTs, vueTsConfigs } from '@vue/eslint-config-typescript'
import pluginVue from 'eslint-plugin-vue'

// Flat config, same set of rules as the old .eslintrc.cjs:
// eslint:recommended + vue3-recommended + the typescript config + prettier
// skip-formatting (prettier owns the formatting, eslint does not touch it).
export default defineConfigWithVueTs(
  {
    name: 'app/files',
    files: ['**/*.{js,mjs,ts,mts,vue}']
  },
  {
    name: 'app/ignores',
    ignores: ['dist/**', 'coverage/**', 'public/**']
  },
  js.configs.recommended,
  pluginVue.configs['flat/recommended'],
  vueTsConfigs.recommended,
  skipFormatting,
  {
    name: 'app/rules',
    rules: {
      // typescript-eslint 8 raised this from warn to error. The code has ~19
      // files with an any, keep the old severity here and clean them up in
      // their own branch.
      '@typescript-eslint/no-explicit-any': 'warn'
    }
  }
)
