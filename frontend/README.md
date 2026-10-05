# Contact Manager Frontend

Next.js, React and TypeScript interface: contact listing, tag filtering,
pagination, contact details, explicit AI summaries, address enrichment and batch
JSON import. Setup, environment variables and backend commands are documented in
the [project README](../README.md).

From this directory, after preparing `.env.local` from `.env.example`:

```sh
npm ci
npm run dev
```

Open `http://localhost:3000`. The API must be running on the configured
`NEXT_PUBLIC_API_URL`. The default local CORS policy allows frontend port 3000.

Validation:

```sh
npm run lint
npm run build
PLAYWRIGHT_MODULE_PATH=/tmp/contact-manager-browser/node_modules/playwright npm run test:browser
```

See [tests/README.md](tests/README.md) for the existing browser test tool setup.
Tests use a mock API and never call OpenAI or ViaCEP.
