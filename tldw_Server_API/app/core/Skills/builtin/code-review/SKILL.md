---
description: Review code for issues across multiple dimensions
argument-hint: "[security|performance|style|all] [code or description]"
context: inline
user_invocable: true
allowed_tools:
  - Read
  - Grep
  - Glob
---

Review the following code. Focus on the specified dimension:

- **security**: Look for vulnerabilities (injection, XSS, auth issues, secret exposure, unsafe deserialization).
- **performance**: Identify bottlenecks, unnecessary allocations, N+1 queries, missing indexes.
- **style**: Check naming conventions, code organization, readability, and adherence to best practices.
- **all**: Cover all of the above dimensions.

If no dimension is specified, default to **all**.

For each issue found, provide:
1. The specific location or line
2. The problem description
3. A suggested fix

Code to review:

$ARGUMENTS
