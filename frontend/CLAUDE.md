# Frontend context

## What this part does
A personal Next.js frontend that serves the UIs of three independent apps backed by the Django backend: **plants** (AI chatbot for plant data), **political-culture** (political chatbot with WebSocket streaming) and **cfflch** (college admission checker: searches admission PDFs over WebSocket and manages the saved results by year).

It lives in `frontend/` of the monorepo, next to the Django backend in `../backend`; the root `CLAUDE.md` has the repository layout and the rules shared with the backend. Paths below are relative to `frontend/`, and `README.md` covers setup, scripts and environment variables. It is deployed as its own Railway service, with Root Directory `/frontend`. It exists to learn and experiment — correctness and understanding over speed.

## Tech stack
- **Framework:** Next.js 16 (App Router, Turbopack for dev and build). Next 16 changed APIs and conventions, so read the relevant guide in `node_modules/next/dist/docs/` (the docs of the installed version) before writing Next-specific code; `AGENTS.md`, which `next dev` writes, says the same for other agents.
- **UI Library:** React 19 + TypeScript 5 (strict mode)
- **Styling:** plain CSS and native HTML elements, no component library (MUI was removed in the redesign), no Tailwind and no PostCSS config. `src/app/globals.css` holds the design tokens and the shared patterns; `data-project="<key>"` sets the app's accent color. Each color token is a `light-dark()` pair, picked by `color-scheme`: it follows the system until the theme switch (`ThemeToggle`) saves a choice in the `theme` cookie (through the `saveTheme` Server Action), which the root layout turns into `<html data-theme>`. Reading that cookie makes every page render on demand. Font: Schibsted Grotesk through `next/font`. UI text is in Portuguese (pt-BR), sentence case.
- **Auth:** Jose 5 for JWT encryption (HS256): the sessions, stored in `httpOnly` cookies and managed via Next.js server actions and the proxy, and the tokens the backend checks
- **HTTP:** Axios for REST calls to the Django backend
- **WebSocket:** Native browser `WebSocket` API (no library), managed via custom hooks
- **Logging:** Client-side logger (`/src/app/api/log/client-logger.ts`) that sends log entries to a Next.js API route (`/api/log`) via Beacon API
- **Markdown:** `react-markdown` + `remark-gfm` for chat message rendering
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
    ├── layout.tsx               # Root layout: font, globals.css, pt-BR, theme cookie
    ├── globals.css              # Design tokens and shared patterns
    ├── projects.ts              # The project list (home page and project switcher)
    ├── page.tsx                 # Home page: the list of projects
    ├── icon.svg                 # Site icon
    ├── actions/                 # Shared session code
    │   ├── api-token.ts         # Server-only: signs the API tokens (user and login)
    │   ├── login-limit.ts       # Server-only: the login attempt limit
    │   ├── session.ts           # "use server": JWT sign/verify, getSession (with the API token), createSession
    │   ├── theme.ts             # "use server": saveTheme, which sets the theme cookie
    │   └── useSession.ts        # Client hook that reads the app's session and API token through getSession
    ├── components/              # Shared infrastructure components
    │   ├── AppHeader.tsx        # App header: project switcher (<details>), the app's nav, theme switch
    │   ├── ThemeToggle.tsx      # Light/dark switch, saves the choice in the "theme" cookie
    │   └── Toast.tsx            # Toast (top-right, hides after 5 s, severity prop)
    ├── api/log/                 # Client log endpoint
    │   ├── route.ts
    │   └── client-logger.ts
    ├── plants/
    │   ├── page.tsx             # Login page
    │   ├── actions/login.ts     # Login server action
    │   ├── components/          # Chat, LoginForm
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
        ├── components/          # login-form, search-form, results-table, result-card
        ├── css/
        ├── hooks/use-admission-search.ts
        ├── types.ts
        └── (routes)/search/ and (routes)/results/
```

### Shared vs app-specific
- **Shared:** session code, the API tokens and the login limit (`src/app/actions/`), the logger (`src/app/api/log/`), the proxy, `globals.css` (tokens; fields, buttons, lists, the login layout, the header, the theme switch, the toast), `projects.ts`, and the infrastructure components `AppHeader`, `ThemeToggle` and `Toast` (`src/app/components/`).
- **App-specific:** everything else, including each app's login server action, feature components, CSS, and hooks. Do not create shared feature UI across apps — duplication is preferred over coupling (each chat keeps its own markup and CSS). Exception: site infrastructure with no app-specific logic, like the header, the theme switch and the toast.

### Adding a project
1. An entry in `src/app/projects.ts` (and its key in `ProjectKey`).
2. An accent color in `globals.css` (light and dark) and its `[data-project="<key>"]` rule.
3. Its routes in the `PROJECTS` map of `src/proxy.ts`.
4. The app folder: a login page with the shared `.auth` classes and `<ThemeToggle />` as the first child of `main.auth`, and `(routes)/layout.tsx` with `<div className="app-shell" data-project="<key>">` and `<AppHeader project="<key>" />`.
5. Its login action, copied from another app's `actions/login.ts` (the attempt limit, `createLoginToken("<key>")`, `createSession(id, "<key>")`), and backend checks with the same key: the key names the session cookie (`session-<key>`) and goes in the token's `app` claim, so a different key on either side gives 401 on every call.

### Proxy
`src/proxy.ts` handles auth routing for all apps. It is what Next.js called middleware before version 16, and it runs on the Node.js runtime (the Edge runtime is not available in a proxy). The `PROJECTS` map must be updated when a new app is added — add the app name, its `publicPaths`, `protectedPaths`, and `defaultProtectedPath`. Each app has its own session cookie, `session-<app>`.

### Auth flow
1. User submits the app's login form → the app's server action `login()` (`src/app/<app>/actions/login.ts`) checks the attempt limit, then calls the backend `GET /api/<app>/users/{name}` with a login token (the name goes through `encodeURIComponent`)
2. On success: `createSession(userId, "<app>")` signs a JWT with Jose (HS256, 7 days) holding the user id and the app, and sets it as the `httpOnly` cookie `session-<app>`. A session only counts for its own app (`decrypt` checks it), so a cookie copied from another app doesn't log in there
3. The proxy reads the cookie on every request: it redirects unauthenticated users from protected pages to `/<app>` (login page), and logged-in users from the login page to the app's default page
4. Client components read the session via the `useSession("<app>")` hook to get `userId` and `token`; it is `undefined` while loading and `null` when there is no valid session. Call the backend only once `token` is there; without a session, show "Não foi possível carregar a sua sessão. Recarregue a página."
5. There is no logout yet (no UI and no action)

`session.ts` is a `"use server"` file, so every export is a Server Action that can be called with a POST request: export only what other modules need. `api-token.ts` and `login-limit.ts` are plain server modules (`import "server-only"`), so their functions can't be called from outside.

### API tokens
Every backend endpoint needs a token: an HS256 JWT signed with `API_TOKEN_SECRET`, the same secret as the backend's (`src/app/actions/api-token.ts`).
- **User token:** `{ sub: "<userId>", app, purpose: "user", iat, exp }`, with the session's own `exp`. `getSession` signs it in the round trip that reads the session. The browser sends `Authorization: Bearer <token>`, and on a WebSocket the subprotocols `["bearer", token]`: a browser can't set headers on a WebSocket, and a query string would end up in access logs.
- **Login token:** `{ app, purpose: "login", iat, exp: iat + 60 }`, signed by each `login()` right before the user lookup.
- The backend answers 401 for a missing or invalid token (expired, another secret, another app, the wrong purpose) and 403 when a user token asks for another user's data (the user id in the path or body must be `sub`). cfflch data has no owner, so any cfflch token reads and changes all of it.
- An axios error carries its request's headers, so the client logger hides `Authorization` before sending a log.

### Login attempt limit
`src/app/actions/login-limit.ts`: 5 wrong names from the same visitor within an hour block that visitor for an hour, in every app (`login()` then answers "Muitas tentativas. Tente de novo em até 1 hora." without calling the backend). The visitor is `x-real-ip` (set by Railway's edge), then the first `x-forwarded-for` entry. Each attempt counts before the lookup, so parallel attempts can't get past the limit; a found name or an error other than a 404 takes its attempt back. Only time clears the wrong names, so logging in with a known name can't reset the limit. The counts live in memory, which is enough for the single Railway instance; they reset on each deploy.

### WebSocket pattern
- **political-culture:** `hooks/useChatSocket.ts` connects on mount to `ws(s)://<server>/ws/chat/<userId>`, so it is open before any message is sent.
- **cfflch:** `hooks/use-admission-search.ts` opens `ws(s)://<server>/ws/cfflch/admission-status/<requestId>` for each search and waits for `onopen` before the POST.
- The backend does not re-deliver messages, so the socket must be open before the POST.
- Both send the API token as the subprotocols `["bearer", token]`, and the backend accepts with `bearer`.

## Coding conventions

### Naming
- Files and folders: `kebab-case` (cfflch follows it; plants, political-culture and the shared `components/` and `actions/` use `PascalCase` component files and `camelCase` hook files)
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
- App-specific CSS in `<app>/css/`, written as plain CSS with the tokens from `globals.css` (`var(--...)`); reuse the shared classes before writing new ones.
- A color that changes with the theme uses a token or `light-dark()`. A `prefers-color-scheme` query would ignore the choice saved by the theme switch.
- Prefix app class names with the app (`plants-chat-…`, `political-chat-…`, `results-…`): Next.js keeps route stylesheets loaded after client-side navigation, so generic names from one app would style another.

### Environment variables
- `NEXT_PUBLIC_SERVER_URL` — the Django backend URL (available client-side). It is inlined at build time, and `next.config.ts` throws when it is missing.
- `SESSION_SECRET` — JWT signing key (server-only, never exposed to client)
- `API_TOKEN_SECRET` — signs the API tokens (server-only); it must be the same value as the backend's `API_TOKEN_SECRET`

## Backend API contract
The Django backend runs at `NEXT_PUBLIC_SERVER_URL`. The endpoints the frontend calls (each app's `api/urls.py` in `../backend` has the full list):

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

Each call carries a token (see API tokens): the login lookups a login token for the app, the rest a user token.

The plants chat endpoints have no `/plants` prefix in the backend, and its GET routes end with a slash.

### cfflch API notes
- **WebSocket must be connected before POST** — results are not re-delivered if the client connects late. This is a known backend constraint, not a bug to work around.
- `pdf_urls` is a `list[dict]` with `url` and `search_title` keys — read `item.url`, not the element directly.

## Current state

### Complete (stable)
- `plants`: login, session, custom chat UI, chat history, message sending, React Markdown rendering
- `political-culture`: login, session, custom chat UI, WebSocket streaming, chat history, React Markdown rendering
- `cfflch`: login, session, search form (names, year, optional class) with results streamed over WebSocket, results page by year with PDF and class filters, and approve, class change and delete on each result

### Known gaps
- No logout in any app; sessions last 7 days.
- No tests (see below).

## Non-negotiables
The shared ones (learning-first, git managed by the user) are in the root `CLAUDE.md`.
- **App isolation.** No shared feature components across apps. Each app owns its full component tree; only site infrastructure (`AppHeader`, `ThemeToggle`, `Toast`, `globals.css`) is shared.
- **Backend contract matters.** The WebSocket-before-POST constraint is non-negotiable: political-culture connects on mount, and cfflch waits for `onopen` before each POST.
- **No tests yet.** Vitest or Jest is not installed. Do not write tests unless explicitly asked.
- **TypeScript strict.** All new code must pass `tsc --noEmit` cleanly.
