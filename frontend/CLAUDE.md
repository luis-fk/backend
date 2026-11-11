# Frontend context

## What this part does
A personal Next.js frontend that serves the UIs of three independent apps backed by the Django backend: **plants** (AI chatbot for plant data), **political-culture** (political chatbot with WebSocket streaming, and the shared library of texts it reads) and **cfflch** (college admission checker: searches admission PDFs over WebSocket and manages the saved results by year).

It lives in `frontend/` of the monorepo, next to the Django backend in `../backend`; the root `CLAUDE.md` has the repository layout and the rules shared with the backend. Paths below are relative to `frontend/`, and `README.md` covers setup, scripts and environment variables. It is deployed as its own Railway service, with Root Directory `/frontend`. It exists to learn and experiment — correctness and understanding over speed.

## Tech stack
- **Framework:** Next.js 16 (App Router, Turbopack for dev and build). Next 16 changed APIs and conventions, so read the relevant guide in `node_modules/next/dist/docs/` (the docs of the installed version) before writing Next-specific code; `AGENTS.md`, which `next dev` writes, says the same for other agents.
- **UI Library:** React 19 + TypeScript 5 (strict mode)
- **Styling:** plain CSS and native HTML elements, no component library (MUI was removed in the redesign), no Tailwind and no PostCSS config. `src/app/globals.css` holds the design tokens and the shared patterns; `data-project="<key>"` sets the app's accent color. Each color token is a `light-dark()` pair, picked by `color-scheme`: it follows the system until the theme switch (`ThemeToggle`) saves a choice in the `theme` cookie (through the `saveTheme` Server Action), which an inline script in the root layout turns into `<html data-theme>` before the first paint. The script goes through `InlineScript`, a Client Component that makes it plain text when React renders it in the browser (switching language remounts the root layout): React never runs such a script, and it warns about one that is JavaScript. The script reads the cookie in the browser because `cookies()` in the root layout would render every page on demand; this way the pages are static (Next's guide "Preventing flash before hydration"), and `ThemeToggle` puts the theme back if React renders `<html>` again in the browser. A page that shows something from the current time calls `await connection()` to render on each request, as the cfflch search and results pages do for their year lists: prerendered, they would keep the build's year. Font: Schibsted Grotesk through `next/font`. UI text is in Brazilian Portuguese and English, in sentence case, from the dictionaries (see Languages).
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
Each app lives under `src/app/[lang]/<app-name>/` and is fully self-contained for UI logic:

```
src/
├── proxy.ts                     # Language and auth routing for all apps
├── types.d.ts                   # Lets TypeScript import .css files
└── app/
    ├── [lang]/                  # Every page, once per language (pt-BR, en)
    │   ├── layout.tsx           # Root layout: <html lang>, font, globals.css, the theme script
    │   ├── page.tsx             # Home page: the list of projects
    │   ├── not-found.tsx        # The 404 page, in the path's language
    │   ├── [...rest]/page.tsx   # Any unknown path: notFound()
    │   ├── plants/
    │   │   ├── page.tsx         # Login page
    │   │   ├── actions/login.ts # Login server action
    │   │   ├── components/      # Chat, LoginForm, Sensors, SensorsChart
    │   │   ├── css/
    │   │   ├── sensors.ts       # The sensors API's types and formatters
    │   │   └── (routes)/chat/ and (routes)/sensors/
    │   ├── political-culture/
    │   │   ├── page.tsx
    │   │   ├── actions/login.ts
    │   │   ├── components/      # Chat, LoginForm, Texts
    │   │   ├── css/
    │   │   ├── hooks/           # useChatSocket.ts, useTextsSocket.ts
    │   │   └── (routes)/chat/ and (routes)/texts/
    │   └── cfflch/
    │       ├── page.tsx
    │       ├── actions/login.ts
    │       ├── components/      # login-form, search-form, results-table, result-card
    │       ├── css/
    │       ├── hooks/use-admission-search.ts
    │       ├── types.ts
    │       └── (routes)/search/ and (routes)/results/
    ├── i18n.ts                  # The languages and the path helpers (localePath, toLocale)
    ├── useLocale.ts             # Client hook: the page's language
    ├── dictionary.ts            # The shared texts in both languages
    ├── globals.css              # Design tokens and shared patterns
    ├── projects.ts              # The project list (home page and project switcher)
    ├── icon.svg                 # Site icon
    ├── actions/                 # Shared session code
    │   ├── api-token.ts         # Server-only: signs the API tokens (user and login)
    │   ├── login-limit.ts       # Server-only: the login attempt limit
    │   ├── session-cookie.ts    # Server-only: the session JWT and its cookie (createSession, decrypt, deleteSession)
    │   ├── session.ts           # "use server": getSession (with the API token) and logout
    │   ├── theme.ts             # "use server": saveTheme, which sets the theme cookie
    │   └── useSession.ts        # Client hook that reads the app's session and API token through getSession
    ├── components/              # Shared infrastructure components
    │   ├── AppHeader.tsx        # App header: project switcher (<details>), the app's nav, language link, theme switch, "Sair"
    │   ├── CornerControls.tsx   # Language link and theme switch for the pages without the header
    │   ├── InlineScript.tsx     # The root layout's theme script: runs before the first paint, plain text when React renders it in the browser
    │   ├── LanguageLink.tsx     # Link to the same page in the other language
    │   ├── ThemeToggle.tsx      # Light/dark switch, saves the choice in the "theme" cookie
    │   └── Toast.tsx            # Toast (top-right, hides after 5 s, severity prop)
    └── api/log/                 # Client log endpoint (outside [lang])
        ├── route.ts
        └── client-logger.ts
```

### Shared vs app-specific
- **Shared:** the languages (`i18n.ts`, `useLocale.ts`, `dictionary.ts`), session code, the API tokens and the login limit (`src/app/actions/`), the logger (`src/app/api/log/`), the proxy, `globals.css` (tokens; fields, buttons, lists, the login layout, the header, the theme switch, the toast), `projects.ts`, and the infrastructure components `AppHeader`, `CornerControls`, `InlineScript`, `LanguageLink`, `ThemeToggle` and `Toast` (`src/app/components/`).
- **App-specific:** everything else, including each app's login server action, feature components, CSS, and hooks. Do not create shared feature UI across apps — duplication is preferred over coupling (each chat keeps its own markup and CSS). Exception: site infrastructure with no app-specific logic, like the header, the theme switch and the toast.

### Adding a project
1. An entry in `src/app/projects.ts` (and its key in `ProjectKey`), and its name and description in both languages in `src/app/dictionary.ts`.
2. An accent color in `globals.css` (light and dark) and its `[data-project="<key>"]` rule.
3. Its routes in the `PROJECTS` map of `src/proxy.ts`.
4. The app folder under `src/app/[lang]/`, with its texts in a `dictionary.ts` of its own: a login page with the shared `.auth` classes and `<CornerControls />` as the first child of `main.auth`, and `(routes)/layout.tsx` with `<div className="app-shell" data-project="<key>">` and `<AppHeader project="<key>" />`.
5. Its login action, copied from another app's `actions/login.ts` (the attempt limit, `createLoginToken("<key>")`, `createSession(id, "<key>")`), and backend checks with the same key: the key names the session cookie (`session-<key>`) and goes in the token's `app` claim, so a different key on either side gives 401 on every call.

### Proxy
`src/proxy.ts` handles the language and auth routing for all apps (see Languages for the language part). It is what Next.js called middleware before version 16, and it runs on the Node.js runtime (the Edge runtime is not available in a proxy). The `PROJECTS` map must be updated when a new app is added — add the app name, its `publicPaths`, `protectedPaths`, and `defaultProtectedPath`. Each app has its own session cookie, `session-<app>`.

### Languages
The site is in Brazilian Portuguese and English, with the language as the first segment of every path (`/pt-BR/plants/chat`, `/en/plants/chat`), as Next's internationalization guide recommends.
- **Routing:** every page lives under `src/app/[lang]/`. The root layout's `generateStaticParams` prerenders each page in both languages, and `dynamicParams = false` turns any other first segment into a 404. `<html lang>` is the segment.
- **Paths without a language** (old links, bookmarks, `/`): the proxy redirects to the same path and query in the `lang` cookie's language, else the browser's (`Accept-Language`), else Portuguese. The proxy sets `lang` (one year) on every page whose language differs from the cookie, so the last language used wins.
- **Texts:** `src/app/dictionary.ts` holds the shared texts and each app's `dictionary.ts` its own, as `Record<Locale, …>`. The English object has the Portuguese one's type (`const en: …Dictionary = …`), so a missing text fails the build; texts with values in them are functions. Server code reads the language with `toLocale((await params).lang)`, client code with `useLocale()`. Every internal link and redirect goes through `localePath(lang, path)`.
- **Numbers** shown to people use `toLocaleString(lang)`; years don't, since pt-BR would print 2.026.
- **Route params:** typed by hand as `{ params: Promise<{ lang: string }> }`. The generated `PageProps`/`LayoutProps` types live in `.next/`, which the CI's typecheck (no build) doesn't have.
- **Language link:** `LanguageLink` points to the same page in the other language, named in it ("English", "Português"); the header on phones shows its code ("EN", "PT"). The header holds it next to the theme switch, and `CornerControls` puts both in the corner of the pages without a header. Its prefetch is off: a prefetch goes through the proxy, which would save the other language in the cookie.
- **Switching language** remounts the page under the new `[lang]`: unsent text and the progress of a running search or upload are dropped, while the search or upload goes on in the backend.
- **404:** an unknown path under a language reaches `[...rest]/page.tsx`, which calls `notFound()`. With the root layout in a dynamic segment, Next's server answers every 404 with an error shell (status 404) and the browser then draws `not-found.tsx` inside the layout. Next's fix for this is the experimental `global-not-found`, which the site doesn't use.

### Auth flow
1. User submits the app's login form → the app's server action `login(lang, formData)` (`src/app/[lang]/<app>/actions/login.ts`), which answers in the page's language (in Portuguese for an unknown one), checks the attempt limit, then calls the backend `GET /api/<app>/users/{name}` with a login token (the name goes through `encodeURIComponent`)
2. On success: `createSession(userId, "<app>")` signs a JWT with Jose (HS256, 7 days) holding the user id and the app, and sets it as the `httpOnly` cookie `session-<app>`. A session only counts for its own app (`decrypt` checks it), so a cookie copied from another app doesn't log in there
3. The proxy reads the cookie on every request: it redirects unauthenticated users from protected pages to `/<lang>/<app>` (login page), and logged-in users from the login page to the app's default page, in the same language
4. Client components read the session via the `useSession("<app>")` hook to get `userId` and `token`; it is `undefined` while loading and `null` when there is no valid session. Call the backend only once `token` is there; without a session, show the common dictionary's `session.loadFailed` (`commonDictionary[lang].session.loadFailed`)
5. "Sair", in the app header, calls the Server Action `logout(lang, "<app>")`: it deletes the app's session cookie and goes back to the login page in the same language. A user token already signed still works until it expires, since the tokens are stateless

`session.ts` is a `"use server"` file, so every export is a Server Action that anyone can call with a POST request: it only exports `getSession` and `logout`, which read or end the caller's own session. `session-cookie.ts` (which creates the session), `api-token.ts` and `login-limit.ts` are plain server modules (`import "server-only"`), so their functions can't be called from outside.

### API tokens
Every backend endpoint needs a token: an HS256 JWT signed with `API_TOKEN_SECRET`, the same secret as the backend's (`src/app/actions/api-token.ts`).
- **User token:** `{ sub: "<userId>", app, purpose: "user", iat, exp }`, with the session's own `exp`. `getSession` signs it in the round trip that reads the session. The browser sends `Authorization: Bearer <token>`, and on a WebSocket the subprotocols `["bearer", token]`: a browser can't set headers on a WebSocket, and a query string would end up in access logs.
- **Login token:** `{ app, purpose: "login", iat, exp: iat + 60 }`, signed by each `login()` right before the user lookup.
- The backend answers 401 for a missing or invalid token (expired, another secret, another app, the wrong purpose) or for a person blocked in the Django admin (Active, or the app, unticked), and 403 when a user token asks for another user's data (the user id in the path or body must be `sub`). cfflch data has no owner, so any cfflch token reads and changes all of it.
- A blocked person's page says the session expired, and a reload doesn't help, since their session cookie is still valid: only "Sair" leads back to the login, where their name isn't found. The owner chose this over a message of its own.
- An axios error carries its request's headers, so the client logger hides `Authorization` before sending a log.

### Login attempt limit
`src/app/actions/login-limit.ts`: 5 wrong names from the same visitor within an hour block that visitor for an hour, in every app (`login()` then answers its dictionary's `tooManyAttempts`, in the page's language, without calling the backend). The visitor is `x-real-ip` (set by Railway's edge), then the first `x-forwarded-for` entry. Each attempt counts before the lookup, so parallel attempts can't get past the limit; a found name or an error other than a 404 takes its attempt back. Only time clears the wrong names, so logging in with a known name can't reset the limit. The counts live in memory, which is enough for the single Railway instance; they reset on each deploy.

### WebSocket pattern
- **political-culture:** `hooks/useChatSocket.ts` connects on mount to `ws(s)://<server>/ws/chat/<userId>`, so it is open before any message is sent, and `hooks/useTextsSocket.ts` to `ws(s)://<server>/ws/political-culture/texts/<userId>`, which says how each PDF upload ended. Its callbacks go through `useEffectEvent`, so a new callback doesn't reconnect the socket and lose a result. The page picks each upload's id (`crypto.randomUUID()`) and sends it with the file, since a PDF that fails at once can answer before the 202. The page only uploads while the socket is open; a closed socket (a backend deploy closes it) is not reopened, and the page asks for a reload, as the chat does.
- **cfflch:** `hooks/use-admission-search.ts` opens `ws(s)://<server>/ws/cfflch/admission-status/<requestId>` for each search and waits for `onopen` before the POST.
- The backend does not re-deliver messages, so the socket must be open before the POST.
- Both send the API token as the subprotocols `["bearer", token]`, and the backend accepts with `bearer`.
- A failure comes over the socket too, so a page never waits forever: the political-culture chat gets `{ failed: true }` when the answer fails, and a cfflch student comes with `failed: true` when the search couldn't run or read any list.

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
| plants | `/api/plants/devices/` | GET | The person's active sensors (`id`, `nickname`, `last_reading_at`) |
| plants | `/api/plants/devices/{id}/readings/` | GET | One sensor's readings for `hours` = 24, 168 or 720, oldest first; `air_humidity` and `temperature` are null when the weather was missing |
| political-culture | `/api/political-culture/users/{name}` | GET | Login lookup |
| political-culture | `/api/political-culture/chatbot/message` | POST | Sends a chat message (`user_id`, `text`, and the page's `language`, which `/help` answers in); the answer comes via WebSocket |
| political-culture | `/api/political-culture/chat-history/{userId}` | GET | Returns chat history |
| political-culture | `/api/political-culture/texts` | GET | The shared library, newest first |
| political-culture | `/api/political-culture/texts` | POST | Adds a PDF of up to 100 MB (`content`, and the page's `upload_id`): 202, or 409 when it is in the library or being read; the result comes via WebSocket |
| political-culture | `/api/political-culture/texts/{id}/selection` | PUT | `{ selected }`: ticks or unticks the text for the user's analyses |
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
- `plants`: login, session, logout, custom chat UI, chat history, message sending, React Markdown rendering, and the Sensores tab: each plant's soil moisture, air humidity and temperature over 24 h, 7 or 30 days, in a chart drawn in SVG by the app (two panels on one time axis, since % and °C don't share an axis; no chart library). The chart measures its own width so its text keeps its size on a phone, breaks its lines at gaps and empty values, and draws a lone reading as a dot. Its series colors were validated for color blindness on both themes.
- `political-culture`: login, session, logout, custom chat UI, WebSocket streaming, chat history, React Markdown rendering, and the Textos page (the library, the PDF upload with its progress and result, and each user's ticks on the texts the assistant uses in their analyses, all unticked at first). Texts are edited and deleted only in the Django admin.
- `cfflch`: login, session, logout, search form (names, year, optional class) with results streamed over WebSocket, results page by year with PDF and class filters, and approve, class change and delete on each result

### Known gaps
- No tests (see below).

## Non-negotiables
The shared ones (learning-first, git managed by the user) are in the root `CLAUDE.md`.
- **App isolation.** No shared feature components across apps. Each app owns its full component tree; only site infrastructure (`AppHeader`, `CornerControls`, `InlineScript`, `LanguageLink`, `ThemeToggle`, `Toast`, `globals.css`) is shared.
- **Backend contract matters.** The WebSocket-before-POST constraint is non-negotiable: political-culture connects on mount, and cfflch waits for `onopen` before each POST.
- **No tests yet.** Vitest or Jest is not installed. Do not write tests unless explicitly asked.
- **TypeScript strict.** All new code must pass `tsc --noEmit` cleanly.
