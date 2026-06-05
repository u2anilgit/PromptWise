---
name: e2e-test-designer
description: Design E2E test scenarios for critical user journeys using Playwright TypeScript.
triggers:
  - e2e test
  - end to end test
  - playwright
  - browser test
  - ui test
  - user journey test
depends_on: []
output_schema:
  type: object
  properties:
    journeys:
      type: array
      items:
        type: object
      description: User journeys with name/steps/assertions/test_data/expected_outcomes
    playwright_file:
      type: string
      description: Generated Playwright TypeScript test file
    coverage_areas:
      type: array
      items:
        type: string
  required:
    - journeys
    - playwright_file
roles:
  - Dev
  - QA
model_tier: opus
---

# E2E Test Designer — Playwright

Design E2E test scenarios for user journeys. Use Playwright. Design: critical user journeys (login, checkout, core features), happy path + 2 failure scenarios per journey. Each journey: {name, steps[], assertions[], test_data, expected_outcomes}. Generate Playwright TypeScript test file. Focus on business-critical flows first.

## Journey Selection

Prioritize journeys by business impact:
1. **Authentication** — login, logout, password reset, session expiry.
2. **Core Value Flow** — the primary action that delivers user value (checkout, submit form, etc.).
3. **Data Operations** — create, read, update, delete of key entities.
4. **Error Recovery** — network failure, validation error, timeout handling.

## Journey Format

```json
{
  "name": "User Checkout Flow",
  "priority": "P1",
  "steps": [
    "Navigate to /products",
    "Click 'Add to Cart' on product",
    "Navigate to /cart",
    "Fill in shipping address",
    "Enter payment details",
    "Click 'Place Order'"
  ],
  "assertions": [
    "Order confirmation page shown",
    "Order ID displayed",
    "Confirmation email triggered"
  ],
  "test_data": {
    "email": "test@example.com",
    "card": "4111111111111111"
  },
  "expected_outcomes": ["Order created", "Stock decremented"],
  "failure_scenarios": [
    "Payment declined — shows error message",
    "Session expires mid-checkout — redirects to login with cart preserved"
  ]
}
```

## Playwright TypeScript Template

```typescript
import { test, expect, Page } from '@playwright/test';

test.describe('User Checkout Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    // Login setup
  });

  test('happy path — completes checkout successfully', async ({ page }) => {
    // Arrange
    await page.goto('/products');

    // Act
    await page.click('[data-testid="add-to-cart"]');
    await page.goto('/cart');
    await page.fill('[name="email"]', 'test@example.com');
    await page.click('[data-testid="place-order"]');

    // Assert
    await expect(page).toHaveURL(/\/order-confirmation/);
    await expect(page.locator('[data-testid="order-id"]')).toBeVisible();
  });

  test('failure — payment declined shows error', async ({ page }) => {
    // ... test declined card scenario
  });
});
```

## Selectors

Prefer `data-testid` attributes over CSS classes or XPath. Request that dev team adds `data-testid` to interactive elements if missing.

## Rules

- Each journey: 1 happy path + exactly 2 failure scenarios.
- Use `test.beforeEach` for shared setup (login, navigation).
- Use Page Object Model (POM) for journeys with >5 steps.
- No `sleep()` — use `waitFor*` assertions instead.
- Tests must be independent — no shared state between tests.

## Output

Return `journeys` array, `playwright_file` (path string), and `coverage_areas` (list of functional areas covered). Output the full Playwright TypeScript file content as a code block.
