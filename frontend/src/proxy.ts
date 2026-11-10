import { NextRequest, NextResponse } from "next/server";
import { decrypt } from "@/app/actions/session-cookie";
import { DEFAULT_LOCALE, type Locale, isLocale, localePath } from "@/app/i18n";

// Excludes _next internals, API routes, and any path with a file extension
export const config = {
  matcher: ["/((?!_next/|api/|.*\\..*).*)"],
};

// The last language the visitor used: set on each page with a language, and
// read for a path without one.
const LOCALE_COOKIE = "lang";
const ONE_YEAR_IN_SECONDS = 60 * 60 * 24 * 365;

type ProjectConfig = {
  publicPaths: string[];
  protectedPaths: string[];
  defaultProtectedPath: string;
};

const PROJECTS: Record<string, ProjectConfig> = {
  "political-culture": {
    publicPaths: [""],
    protectedPaths: ["chat", "texts"],
    defaultProtectedPath: "chat",
  },
  plants: {
    publicPaths: [""],
    protectedPaths: ["chat"],
    defaultProtectedPath: "chat",
  },
  cfflch: {
    publicPaths: [""],
    protectedPaths: ["search", "results"],
    defaultProtectedPath: "search",
  },
};

// The visitor's language among the site's, from Accept-Language: the tags in
// order of preference (q=0 means "not this one"); the first Portuguese or
// English one wins, and Portuguese when there is neither.
function pickLocale(acceptLanguage: string | null): Locale {
  const tags = (acceptLanguage ?? "")
    .split(",")
    .map((part) => {
      const [tag, ...params] = part.trim().split(";");
      const q = params
        .map((param) => param.trim())
        .find((param) => param.startsWith("q="));
      return { tag: tag.toLowerCase(), q: q ? Number(q.slice(2)) : 1 };
    })
    .filter(({ tag, q }) => tag && q > 0)
    // A stable sort, so tags with the same q keep their order.
    .sort((a, b) => b.q - a.q);

  for (const { tag } of tags) {
    const language = tag.split("-")[0];
    if (language === "pt") return "pt-BR";
    if (language === "en") return "en";
  }
  return DEFAULT_LOCALE;
}

// Sends a visitor without a session from a protected page to the app's login
// page, and one with a session from the login page into the app, in the same
// language.
async function authRedirect(
  req: NextRequest,
  lang: Locale,
  project: string,
  subPath: string,
): Promise<NextResponse | undefined> {
  if (!Object.hasOwn(PROJECTS, project)) return;
  const cfg = PROJECTS[project];

  const cookie = req.cookies.get(`session-${project}`)?.value;
  const session = await decrypt(cookie, project);

  const isPublic = cfg.publicPaths.some((p) => p === subPath);
  const isProtected = cfg.protectedPaths.some(
    (p) => subPath === p || subPath.startsWith(p + "/"),
  );

  if (isProtected && !session?.userId) {
    return NextResponse.redirect(
      new URL(localePath(lang, `/${project}`), req.nextUrl),
    );
  }

  if (isPublic && session?.userId) {
    return NextResponse.redirect(
      new URL(
        localePath(lang, `/${project}/${cfg.defaultProtectedPath}`),
        req.nextUrl,
      ),
    );
  }
}

export default async function proxy(req: NextRequest): Promise<NextResponse> {
  const { pathname } = req.nextUrl;
  const [lang, project = "", ...rest] = pathname.split("/").filter(Boolean);

  // Without a language: the same path and query in the remembered language,
  // else the browser's.
  if (!lang || !isLocale(lang)) {
    const saved = req.cookies.get(LOCALE_COOKIE)?.value;
    const url = req.nextUrl.clone();
    url.pathname = localePath(
      saved && isLocale(saved)
        ? saved
        : pickLocale(req.headers.get("accept-language")),
      pathname,
    );
    return NextResponse.redirect(url);
  }

  const response =
    (await authRedirect(req, lang, project, rest.join("/"))) ??
    NextResponse.next();
  if (req.cookies.get(LOCALE_COOKIE)?.value !== lang) {
    response.cookies.set(LOCALE_COOKIE, lang, {
      maxAge: ONE_YEAR_IN_SECONDS,
      sameSite: "lax",
      path: "/",
    });
  }
  return response;
}
