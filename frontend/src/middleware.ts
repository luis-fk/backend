import { NextRequest, NextResponse } from "next/server";
import { decrypt } from "@/app/actions/session";

// Excludes _next internals, API routes, and any path with a file extension
export const config = {
  matcher: ["/((?!_next/|api/|.*\\..*).*)",],
};

type ProjectConfig = {
  publicPaths: string[];
  protectedPaths: string[];
  defaultProtectedPath: string;
};

const PROJECTS: Record<string, ProjectConfig> = {
  "political-culture": {
    publicPaths: [""],
    protectedPaths: ["chat"],
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

export default async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;

  const segments = pathname.split("/").filter(Boolean);
  const project = segments[0];
  const subPath = segments.slice(1).join("/");

  const cfg = PROJECTS[project];

  if (!cfg) {
    return NextResponse.next();
  }

  const cookie = req.cookies.get("session")?.value;
  const session = await decrypt(cookie);

  const isPublic = cfg.publicPaths.some((p) => p === subPath);
  const isProtected = cfg.protectedPaths.some(
    (p) => subPath === p || subPath.startsWith(p + "/"),
  );

  if (isProtected && !session?.userId) {
    return NextResponse.redirect(new URL(`/${project}`, req.nextUrl));
  }

  if (isPublic && session?.userId) {
    return NextResponse.redirect(
      new URL(`/${project}/${cfg.defaultProtectedPath}`, req.nextUrl),
    );
  }

  return NextResponse.next();
}