# Browser validation

The tests use Node's built-in test runner and Playwright with an installed Chrome.
They start an isolated mock API and a production Next.js server, cover contact
detail actions, and restore a normal production build during cleanup. No request
is forwarded to OpenAI or ViaCEP. Project dependencies are unchanged.

From `frontend`, using the Playwright installation available in this workspace:

```sh
PLAYWRIGHT_MODULE_PATH=/tmp/contact-manager-browser/node_modules/playwright npm run test:browser
```

If Playwright is already installed elsewhere, set `PLAYWRIGHT_MODULE_PATH` to its
module path. If it is available in normal Node resolution, omit that variable.
Chrome must be installed. The mock API uses port 8011 and Next.js uses port 3001;
override `TEST_API_PORT` and `TEST_FRONTEND_PORT` when those ports are occupied.

The suite builds Next.js with the mock API URL before testing. Do not run builds
concurrently with this suite. No `.env` files are opened or modified by the test
code, and only the public API URL is overridden for the isolated build.
