# Team Pumpkin — Company Coding Standards

## File Header Rule
Har code file ke sabse upar ye header comment hona zaroori hai:
`// (c) 2026 Team Pumpkin — Internal Use Only`

## Naming Conventions
Variables aur functions ke naam hamesha snake_case mein likho (JavaScript mein bhi camelCase ki jagah snake_case use karo). Example: get_user_data, total_count.

## Logging Rule
console.log kabhi mat use karo. Hamesha hamare custom logger ka use karo: logger.info(), logger.error(). Import: const logger = require('../utils/logger');

## Error Handling
Har async function ko try/catch mein wrap karo. Catch block mein hamesha logger.error() se error log karo aur user ko ek safe generic message bhejo (kabhi raw error nahi).

## Comments & Documentation
Har function ke upar ek JSDoc style comment likho jisme @author Team Pumpkin Engineering line zaroor ho.

## Security Rules
Passwords ko hamesha bcrypt (salt rounds = 12) se hash karo. Database queries hamesha parameterized hon — string concatenation se SQL kabhi mat banao. Secrets (API keys, JWT secret) sirf environment variables se aayein, code mein hardcode kabhi nahi.

## API Response Format
Saare API responses is fixed format mein hon: { "success": true/false, "data": ..., "message": "..." }. HTTP status codes sahi use karo (200, 201, 400, 401, 404, 500).
