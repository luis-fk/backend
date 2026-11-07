# Frontend context

## What this part does
A personal Next.js frontend that serves multiple independent apps backed by a Django backend. Currently hosts two apps — **plants** (AI chatbot for plant data) and **political-culture** (political text chatbot with WebSocket streaming) — with a third app **cfflch** (college admission checker) missing from the frontend and needing to be built.

It lives in `frontend/` of the monorepo, next to the Django backend in `../backend`; the root `CLAUDE.md` has the repository layout and the rules shared with the backend. Paths below are relative to `frontend/`. It is deployed as its own Railway service, with Root Directory `/frontend`. It exists to learn and experiment — correctness and understanding over speed.

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
- **Linting:** ESLint 9 flat config (`eslint.config.mjs` with `eslint-config-next`, run by `npm run lint` = `eslint .`; `next lint` no longer exists) + Prettier 3 with `@trivago/prettier-plugin-sort-imports`. `react-hooks/set-state-in-effect`, new in `eslint-plugin-react-hooks` 7, is a warning until the existing effects that set state on mount are refactored.
- **Package manager:** npm. Exact versions live in `package.json`.
- **Security overrides:** Railway's build scanner blocks lockfiles with vulnerable dependencies (confirmed for Next.js advisories rated high or critical; the full rule is not documented), so keep `npm audit --audit-level=high` clean. `overrides` in `package.json` forces a patched `minimatch` inside `prettier-eslint` → `@typescript-eslint/typescript-estree@6`, which pins 9.0.3. Drop it when `prettier-eslint` moves to 17, which is ESM-only and not yet supported by the VS Code extension `rvest.vs-code-prettier-eslint` (it expects ^16).

## Architecture

### Multi-app structure
Each app lives under `src/app/<app-name>/` and is fully self-contained for UI logic:

```
src/
├── proxy.ts                     # Auth routing for all projects
├── app/
│   ├── layout.tsx               # Root layout
│   ├── page.tsx                 # Landing page (links to each app)
│   ├── actions/                 # Shared server actions
│   │   ├── login.ts             # Login logic (calls backend /api/user/{name})
│   │   ├── session.ts           # JWT encrypt/decrypt/create/delete
│   │   └── useSession.ts        # Client-side session hook
│   ├── components/              # Shared infrastructure components
│   │   └── Toast.tsx            # MUI Snackbar/Alert toast (top-right, 5s, severity prop)
│   ├── api/log/                 # Server-side log endpoint
│   │   ├── route.ts
│   │   └── client-logger.ts
│   ├── plants/                  # Plants app
│   │   ├── components/
│   │   ├── css/
│   │   └── (routes)/chat/
│   └── political-culture/       # Political-culture app
│       ├── components/
│       ├── css/
│       ├── hooks/
│       └── (routes)/chat/
```

### Shared vs app-specific
- **Shared:** auth actions (`session.ts`, `login.ts`, `useSession.ts`), the logger, the proxy, and infrastructure UI components (`src/app/components/`). These live in `src/app/actions/`, `src/app/api/`, and `src/app/components/`.
- **App-specific:** all feature components, CSS, and hooks. Do not create shared feature UI across apps — duplication is preferred over coupling. Exception: pure infrastructure components with no app-specific logic (e.g. `ErrorToast`) may live in `src/app/components/`.

### Proxy
`src/proxy.ts` handles auth routing for all apps. It is what Next.js called middleware before version 16, and it runs on the Node.js runtime (the Edge runtime is not available in a proxy). The `PROJECTS` map must be updated when a new app is added — add the app name, its `publicPaths`, `protectedPaths`, and `defaultProtectedPath`.

### Auth flow
1. User submits login form → server action `login()` calls backend `POST /api/user/{name}`
2. On success: `createSession(userId)` encrypts a JWT with Jose (HS256) and sets an `httpOnly` cookie
3. The proxy reads the cookie on every request and redirects unauthenticated users to `/<app>` (login page)
4. Client components read the session via `useSession()` hook to get `userId`

### WebSocket pattern
- Used in `political-culture` for streaming chat responses
- Custom hook in `hooks/useChatSocket.ts` manages the connection lifecycle
- **The WebSocket is established on component mount** (when the chat page loads), so it is always connected before a message is sent — this matches the backend constraint that the client must connect before the POST
- URL pattern: `ws(s)://<server>/<app>/ws/chat/<userId>`

## Coding conventions

### Naming
- Files and folders: `kebab-case`
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
- `(routes)/<route>/page.tsx` — page components (route group with parentheses keeps routes clean)

### CSS
- App-specific CSS in `<app>/css/`, written as plain CSS (Tailwind was removed with the Next 16 upgrade; it was configured but no CSS file loaded it)

### Environment variables
- `NEXT_PUBLIC_SERVER_URL` — the Django backend URL (available client-side)
- `SESSION_SECRET` — JWT signing key (server-only, never exposed to client)

## Backend API contract
The Django backend runs at `NEXT_PUBLIC_SERVER_URL`. Key endpoints:

| App | Endpoint | Method | Notes |
|---|---|---|---|
| Auth | `/api/user/{name}` | GET | Returns user object with `id` on success |
| plants | `/api/plants/chatbot/message` | POST | Sends a chat message |
| plants | `/api/plants/chat-history/{userId}` | GET | Returns chat history |
| political-culture | `/api/political-culture/chatbot/message` | POST | Sends chat message; response comes via WebSocket |
| political-culture | `/api/political-culture/chat-history/{userId}` | GET | Returns chat history |
| cfflch | `/api/cfflch/admission-status/` | POST | Triggers admission search; results come via WebSocket |
| cfflch | WebSocket | WS | `ws(s)://<server>/ws/cfflch/<userId>` — connect BEFORE POST |

### cfflch API notes (for when this is built)
- **WebSocket must be connected before POST** — results are not re-delivered if the client connects late. This is a known backend constraint, not a bug to work around.
- The POST returns `pdf_urls` as `list[dict]` with `url` and `search_title` keys — read `item.url`, not the element directly.

## Current state

### Complete (stable)
- `plants`: login, session, chat UI (Chatscope), chat history, message sending
- `political-culture`: login, session, custom chat UI, WebSocket streaming, chat history, React Markdown rendering

### Missing (not yet built)
- `cfflch`: the backend is fully implemented (admission status checker via web search + PDF parsing + WebSocket). The frontend app does not exist yet.

## Non-negotiables
The shared ones (learning-first, git managed by the user) are in the root `CLAUDE.md`.
- **App isolation.** No shared UI components across apps. Each app owns its full component tree.
- **Backend contract matters.** When building the cfflch frontend, the WS-before-POST timing constraint is non-negotiable — the component must establish the WebSocket connection on mount, not when the user submits.
- **No tests yet.** Vitest or Jest is not installed. Do not write tests unless explicitly asked.
- **TypeScript strict.** All new code must pass `tsc --noEmit` cleanly.