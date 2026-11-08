# Frontend context

## What this part does
A personal Next.js frontend that serves the UIs of three independent apps backed by the Django backend: **plants** (AI chatbot for plant data), **political-culture** (political chatbot with WebSocket streaming) and **cfflch** (college admission checker: searches admission PDFs over WebSocket and manages the saved results by year).

It lives in `frontend/` of the monorepo, next to the Django backend in `../backend`; the root `CLAUDE.md` has the repository layout and the rules shared with the backend. Paths below are relative to `frontend/`, and `README.md` covers setup, scripts and environment variables. It is deployed as its own Railway service, with Root Directory `/frontend`. It exists to learn and experiment — correctness and understanding over speed.

## Tech stack
- **Framework:** Next.js 16 (App Router, Turbopack for dev and build). Next 16 changed APIs and conventions, so read the relevant guide in `node_modules/next/dist/docs/` (the docs of the installed version) before writing Next-specific code; `AGENTS.md`, which `next dev` writes, says the same for other agents.
- **UI Library:** React 19 + TypeScript 5 (strict mode)
- **Styling:** Material-UI 6 (with Emotion) for components and plain CSS files for component-specific styles. There is no Tailwind and no PostCSS config.
- **Auth:** Jose 5 for JWT encryption (HS256), stored in `httpOnly` cookies, managed via Next.js server actions and the proxy
- **HTTP:** Axios for REST calls to the Django backend
- **WebSocket:** Native browser `WebSocket` API (no library), managed via custom hooks
- **Logging:** Client-side logger (`/src/app/api/log/client-logger.ts`) that sends log entries to a Next.js API route (`/api/log`) via Beacon API
- **Markdown:** `react-markdown` + `remark-gfm` for chat message rendering
- **Chat UI:** `@chatscope/chat-ui-kit-react` (used in `plants` only)
- **Linting:** ESLint 9 flat config (`eslint.config.mjs` with `eslint-config-next`, run by `npm run lint` = `eslint .`; `next lint` no longer exists) + Prettier 3 with `@trivago/prettier-plugin-sort-imports`. `react-hooks/set-state-in-effect` (new in `eslint-plugin-react-hooks` 7) is an error: derive the value or set state in callbacks and event handlers, never synchronously in the effect body.
- **Package manager:** npm. Exact versions live in `package.json`.
- **Node.js:** 22, pinned in `engines.node` in `package.json`. Railway's Nixpacks builder and the CI (`node-version-file`) both read it; without it Nixpacks falls back to Node 18, which Next 16 refuses (it needs 20.9 or newer). Locally, `nvm use 22`.
- **Security overrides:** Railway's build scanner blocks lockfiles with vulnerable dependencies (confirmed for Next.js advisories rated high or critical; the full rule is not documented), so keep `npm audit --audit-level=high` clean. `overrides` in `package.json` forces a patched `minimatch` inside `prettier-eslint` → `@typescript-eslint/typescript-estree@6`, which pins 9.0.3. Drop it when `prettier-eslint` moves to 17, which is ESM-only and not yet supported by the VS Code extension `rvest.vs-code-prettier-eslint` (it expects ^16).

## Architecture

### Multi-app structure
Each app lives under `src/app/<app-name>/` and is fully self-contained for UI logic:

```
src/
├── proxy.ts                     # Auth routing for all apps
├── types.d.ts                   # Lets TypeScript import .css files
└── app/
    ├── layout.tsx               # Root layout
    ├── page.tsx                 # Landing page (links to each app), styled by main-page.css
    ├── actions/                 # Shared session code
    │   ├── session.ts           # "use server": JWT sign/verify, getSession, createSession
    │   └── useSession.ts        # Client hook that reads the app's session through getSession
    ├── components/              # Shared infrastructure components
    │   └── Toast.tsx            # MUI Snackbar/Alert toast (top-right, 5s, severity prop)
    ├── api/log/                 # Client log endpoint
    │   ├── route.ts
    │   └── client-logger.ts
    ├── plants/
    │   ├── page.tsx             # Login page
    │   ├── actions/login.ts     # Login server action
    │   ├── components/          # Chat, LoginForm, MuiDrawer
    │   ├── css/
    │   └── (routes)/chat/
    ├── political-culture/
    │   ├── page.tsx
    │   ├── actions/login.ts
    │   ├── components/          # Chat, LoginForm
    │   ├── css/
    │   ├── hooks/useChatSocket.ts
    │   └── (routes)/chat/
    └── cfflch/
        ├── page.tsx
        ├── actions/login.ts
        ├── components/          # login-form, mui-drawer, search-form, results-table, result-card
        ├── css/
        ├── hooks/use-admission-search.ts
        ├── types.ts
        └── (routes)/search/ and (routes)/results/
```

### Shared vs app-specific
- **Shared:** session code (`src/app/actions/`), the logger (`src/app/api/log/`), the proxy, and infrastructure UI components (`src/app/components/`).
- **App-specific:** everything else, including each app's login server action, feature components, CSS, and hooks. Do not create shared feature UI across apps — duplication is preferred over coupling. Exception: pure infrastructure components with no app-specific logic (e.g. `Toast`) may live in `src/app/components/`.

### Proxy
`src/proxy.ts` handles auth routing for all apps. It is what Next.js called middleware before version 16, and it runs on the Node.js runtime (the Edge runtime is not available in a proxy). The `PROJECTS` map must be updated when a new app is added — add the app name, its `publicPaths`, `protectedPaths`, and `defaultProtectedPath`. Each app has its own session cookie, `session-<app>`.

### Auth flow
1. User submits the app's login form → the app's server action `login()` (`src/app/<app>/actions/login.ts`) calls the backend `GET /api/<app>/users/{name}`
2. On success: `createSession(userId, "session-<app>")` signs a JWT with Jose (HS256, 7 days) and sets it as an `httpOnly` cookie
3. The proxy reads the cookie on every request: it redirects unauthenticated users from protected pages to `/<app>` (login page), and logged-in users from the login page to the app's default page
4. Client components read the session via the `useSession("<app>")` hook to get `userId`; it is `undefined` while loading and `null` when there is no valid session
5. There is no logout yet (no UI and no action)

`session.ts` is a `"use server"` file, so every export is a Server Action that can be called with a POST request: export only what other modules need.

### WebSocket pattern
- **political-culture:** `hooks/useChatSocket.ts` connects on mount to `ws(s)://<server>/ws/chat/<userId>`, so it is open before any message is sent.
- **cfflch:** `hooks/use-admission-search.ts` opens `ws(s)://<server>/ws/cfflch/admission-status/<requestId>` for each search and waits for `onopen` before the POST.
- The backend does not re-deliver messages, so the socket must be open before the POST.

## Coding conventions

### Naming
- Files and folders: `kebab-case` (cfflch follows it; plants and political-culture predate the rule and still use `PascalCase` component files and `camelCase` hook files)
- Components: `PascalCase`
- Hooks: `camelCase` with `use` prefix
- Server actions: `camelCase`
- CSS classes: `kebab-case`

### TypeScript
- Strict mode is on — all code must satisfy `tsc --noEmit`
- Explicit return types on all functions except trivially obvious assignments
- No `any` — use proper types or `unknown` with narrowing

### File structure per app
- `components/` — React components
- `css/` — component-specific CSS files (one per component)
- `hooks/` — custom hooks (only if needed; short hooks can live in the component file)
- `actions/` — the app's server actions (`login.ts`)
- `(routes)/<route>/page.tsx` — page components (route group with parentheses keeps routes clean)

### CSS
- App-specific CSS in `<app>/css/`, written as plain CSS (Tailwind was removed with the Next 16 upgrade; it was configured but no CSS file loaded it)

### Environment variables
- `NEXT_PUBLIC_SERVER_URL` — the Django backend URL (available client-side). It is inlined at build time, and `next.config.ts` throws when it is missing.
- `SESSION_SECRET` — JWT signing key (server-only, never exposed to client)

## Backend API contract
The Django backend runs at `NEXT_PUBLIC_SERVER_URL`. The endpoints the frontend calls (`../backend/README.md` lists all of them):

| App | Endpoint | Method | Notes |
|---|---|---|---|
| plants | `/api/plants/users/{name}/` | GET | Login lookup; returns the user with its `id` |
| plants | `/api/chatbot/message` | POST | Sends a chat message; the answer comes in the response |
| plants | `/api/chat-history/{userId}/` | GET | Returns chat history |
| political-culture | `/api/political-culture/users/{name}` | GET | Login lookup |
| political-culture | `/api/political-culture/chatbot/message` | POST | Sends a chat message; the answer comes via WebSocket |
| political-culture | `/api/political-culture/chat-history/{userId}` | GET | Returns chat history |
| cfflch | `/api/cfflch/users/{name}` | GET | Login lookup |
| cfflch | `/api/cfflch/admission-status/` | POST | Starts an admission search; results come via WebSocket |
| cfflch | `/api/cfflch/admission-results/` | GET | Saved results for a `year` |
| cfflch | `/api/cfflch/admission-results/{id}/` | PATCH, DELETE | Updates `approved` or `class_room_id`, or deletes the result |
| cfflch | `/api/cfflch/class-rooms/` | GET | Class rooms, used by the filters and the result cards |

The plants chat endpoints have no `/plants` prefix in the backend. The plants GET calls leave out the trailing slash, and Django redirects them (301).

### cfflch API notes
- **WebSocket must be connected before POST** — results are not re-delivered if the client connects late. This is a known backend constraint, not a bug to work around.
- `pdf_urls` is a `list[dict]` with `url` and `search_title` keys — read `item.url`, not the element directly.

## Current state

### Complete (stable)
- `plants`: login, session, chat UI (Chatscope), chat history, message sending
- `political-culture`: login, session, custom chat UI, WebSocket streaming, chat history, React Markdown rendering
- `cfflch`: login, session, search form (names, year, optional class) with results streamed over WebSocket, results page by year with PDF and class filters, and approve, class change and delete on each result

### Known gaps
- No logout in any app; sessions last 7 days.
- No tests (see below).

## Non-negotiables
The shared ones (learning-first, git managed by the user) are in the root `CLAUDE.md`.
- **App isolation.** No shared UI components across apps. Each app owns its full component tree.
- **Backend contract matters.** The WebSocket-before-POST constraint is non-negotiable: political-culture connects on mount, and cfflch waits for `onopen` before each POST.
- **No tests yet.** Vitest or Jest is not installed. Do not write tests unless explicitly asked.
- **TypeScript strict.** All new code must pass `tsc --noEmit` cleanly.
