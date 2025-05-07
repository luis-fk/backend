import { NextRequest, NextResponse } from "next/server";
import { decrypt } from "@/app/actions/session";

export const config = {
  matcher: ["/:project/:path*", "/:project"],
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
};

export default async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;

  if (
    pathname.startsWith("/api") ||
    pathname.startsWith("/_next/") ||
    /\.(?:png|jpg|svg|css|js)$/.test(pathname)
  ) {
    return NextResponse.next();
  }

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
