import js from '@eslint/js';
import globals from 'globals';

export default [
  { ignores: ['node_modules/**', 'dist/motion.js', 'outputs/**', 'src/**'] },
  {
    files: ['dist/app.js', 'dist/api.js', 'dist/features.js', 'dist/data.js', 'dist/config.js', 'dist/p1.js', 'dist/p2.js', 'dist/p3.js'],
    ...js.configs.recommended,
    languageOptions: { ecmaVersion: 'latest', sourceType: 'module', globals: globals.browser },
    rules: { ...js.configs.recommended.rules, 'no-unused-vars': ['error', { caughtErrors: 'none' }] }
  }
];
