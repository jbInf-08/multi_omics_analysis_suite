import js from '@eslint/js';
import globals from 'globals';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import tseslint from 'typescript-eslint';

/**
 * ESLint flat config.
 *
 * The `lint` script referenced eslint before this existed, but eslint was not
 * a dependency, there was no config file, and the script passed `--ext`, which
 * ESLint 10 removed. The script could therefore never run; it is now a real
 * check and the CI lint job runs it.
 */
export default tseslint.config(
  {
    ignores: ['dist/**', 'coverage/**', 'node_modules/**'],
  },

  js.configs.recommended,
  ...tseslint.configs.recommended,

  {
    files: ['src/**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: {
        ...globals.browser,
      },
      parserOptions: {
        ecmaFeatures: { jsx: true },
      },
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],

      // Advisory rather than blocking. The one site that trips this polls a
      // task status with react-query and reacts to the terminal state by
      // setting local state and firing a one-shot toast. Deriving that state
      // instead of mirroring it is the idiomatic fix, but it has to keep the
      // toast firing exactly once, so it is a deliberate refactor rather than
      // something to force as part of introducing this config.
      'react-hooks/set-state-in-effect': 'warn',

      // Unused bindings prefixed with _ are deliberate.
      '@typescript-eslint/no-unused-vars': [
        'error',
        {
          argsIgnorePattern: '^_',
          varsIgnorePattern: '^_',
          caughtErrorsIgnorePattern: '^_',
        },
      ],
    },
  },

  {
    // Vitest globals are enabled via test.globals in vite.config.ts.
    files: ['src/**/*.{test,spec}.{ts,tsx}'],
    languageOptions: {
      globals: {
        ...globals.node,
      },
    },
  },

  {
    // Config files run in Node.
    files: ['*.config.{js,ts}', 'vite.config.ts'],
    languageOptions: {
      globals: { ...globals.node },
    },
  }
);
