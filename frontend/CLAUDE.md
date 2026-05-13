# Project context

## What this project does
A personal Next.js frontend that serves multiple independent apps backed by a Django backend. Currently hosts two apps — **plants** (AI chatbot for plant data) and **political-culture** (political text chatbot with WebSocket streaming) — with a third app **cfflch** (college admission checker) missing from the frontend and needing to be built.

The React frontend is a separate deployment from the Django backend. It exists to learn and experiment — correctness and understanding over speed.

## Tech stack
- **Framework:** Next.js 15.1.6 (App Router, Turbopack in dev)
- **UI Library:** React 18.2.0 + TypeScript 4.9.5 (strict mode)
- **Styling:** Material-UI 6.4.1 (with Emotion) + Tailwind CSS 3.4.1 — MUI for components, Tailwind for utility classes. Both coexist; keep new code consistent with the surrounding file.
- **Auth:** Jose 5.9.6 for JWT encryption (HS256), stored in `httpOnly` cookies, managed via Next.js server actions and middleware
- **HTTP:** Axios for REST calls to the Django backend
- **WebSocket:** Native browser `WebSocket` API (no library), managed via custom hooks
- **Logging:** Client-side logger (`/src/app/api/log/client-logger.ts`) that sends log entries to a Next.js API route (`/api/log`) via Beacon API
- **Markdown:** `react-markdown` + `remark-gfm` for chat message rendering
- **Chat UI:** `@chatscope/chat-ui-kit-react` (used in `plants` only)
- **Linting:** ESLint 8.57.1 + Prettier 3.4.2 with `@trivago/prettier-plugin-sort-imports`
- **Package manager:** npm

## Architecture

### Multi-app structure
Each app lives under `src/app/<app-name>/` and is fully self-contained for UI logic:

```
src/
├── app/
│   ├── layout.tsx               # Root layout
│   ├── page.tsx                 # Landing page (links to each app)
│   ├── middleware.tsx            # Auth routing for all projects
│   ├── actions/                 # Shared server actions
│   │   ├── login.ts             # Login logic (calls backend /api/user/{name})
│   │   ├── session.ts           # JWT encrypt/decrypt/create/delete
│   │   └── useSession.ts        # Client-side session hook
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
- **Shared:** auth actions (`session.ts`, `login.ts`, `useSession.ts`), the logger, middleware. These live in `src/app/actions/` and `src/app/api/`.
- **App-specific:** all components, CSS, and hooks. Do not create shared UI components across apps — duplication is preferred over coupling, matching the backend's Parnas decomposition philosophy.

### Middleware
`src/middleware.tsx` handles auth routing for all apps. The `PROJECTS` map must be updated when a new app is added — add the app name, its `publicPaths`, `protectedPaths`, and `defaultProtectedPath`.

### Auth flow
1. User submits login form → server action `login()` calls backend `POST /api/user/{name}`
2. On success: `createSession(userId)` encrypts a JWT with Jose (HS256) and sets an `httpOnly` cookie
3. Middleware reads the cookie on every request and redirects unauthenticated users to `/<app>` (login page)
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
- App-specific CSS in `<app>/css/`
- Use Tailwind for layout and spacing; use custom CSS for component-specific styles not easily expressed in Tailwind
- Do not mix inline styles with Tailwind — pick one per component

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
- **Learning-first.** Correct and understood > fast. Explain the why, not just the what.
- **App isolation.** No shared UI components across apps. Each app owns its full component tree.
- **Git is managed by the user.** Do not commit, push, or open PRs unless explicitly asked.
- **Backend contract matters.** When building the cfflch frontend, the WS-before-POST timing constraint is non-negotiable — the component must establish the WebSocket connection on mount, not when the user submits.
- **No tests yet.** Vitest or Jest is not installed. Do not write tests unless explicitly asked.
- **TypeScript strict.** All new code must pass `tsc --noEmit` cleanly.