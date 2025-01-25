module.exports = {
  // ... other ESLint config options ...
  overrides: [
    {
      files: ['*.ts', '*.tsx'],
      options: {
        parser: '@typescript-eslint/parser',
        plugins: ['@typescript-eslint', 'prettier'],
        rules: {
          '@typescript-eslint/semi': ['error', 'always'],
          '@typescript-eslint/quotes': ['error', 'single'],
          '@typescript-eslint/indent': ['error', 2],
          '@typescript-eslint/no-unused-vars': 'error',
          '@typescript-eslint/no-console': 'warn',
          'prettier/prettier': ['error', {
            printWidth: 80,
            tabWidth: 2,
            useTabs: false,
            semi: true,
            singleQuote: true,
            trailingComma: 'all',
          }],
        },
      },
    },
  ],
};