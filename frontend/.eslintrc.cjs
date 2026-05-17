module.exports = {
    root: true,
    ignorePatterns: ['dist/', 'node_modules/'],
    env: {
        browser: true,
        es2020: true,
    },
    extends: [
        'eslint:recommended',
        'plugin:react/recommended',
        'plugin:react/jsx-runtime',
        'plugin:react-hooks/recommended',
    ],
    parserOptions: {
        ecmaVersion: 'latest',
        sourceType: 'module',
        ecmaFeatures: {
            jsx: true,
        },
    },
    settings: {
        react: {
            version: 'detect',
        },
    },
    plugins: ['react-refresh'],
    rules: {
        'react/prop-types': 'off',
        'react-refresh/only-export-components': 'off',
    },
}
