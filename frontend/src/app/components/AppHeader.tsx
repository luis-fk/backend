"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";
import { logout } from "@/app/actions/session";
import LanguageLink from "@/app/components/LanguageLink";
import ThemeToggle from "@/app/components/ThemeToggle";
import { commonDictionary } from "@/app/dictionary";
import { localePath } from "@/app/i18n";
import { PROJECTS, type ProjectKey } from "@/app/projects";
import { useLocale } from "@/app/useLocale";

type NavLink = { href: string; label: string };

interface AppHeaderProps {
  project: ProjectKey;
  links?: NavLink[];
}

export default function AppHeader({
  project,
  links = [],
}: AppHeaderProps): React.ReactElement {
  const pathname = usePathname();
  const lang = useLocale();
  const menuRef = useRef<HTMLDetailsElement>(null);
  const t = commonDictionary[lang];
  const name = t.projects[project].name;

  // A <details> only closes from its own summary; close it on Escape or a click outside.
  useEffect(() => {
    function closeMenu(event: PointerEvent | KeyboardEvent): void {
      const menu = menuRef.current;
      if (!menu?.open) return;
      if (event instanceof KeyboardEvent) {
        if (event.key !== "Escape") return;
        const focusWasInside = menu.contains(document.activeElement);
        menu.open = false;
        if (focusWasInside) menu.querySelector("summary")?.focus();
        return;
      }
      if (event.target instanceof Node && !menu.contains(event.target)) {
        menu.open = false;
      }
    }

    document.addEventListener("pointerdown", closeMenu);
    document.addEventListener("keydown", closeMenu);
    return () => {
      document.removeEventListener("pointerdown", closeMenu);
      document.removeEventListener("keydown", closeMenu);
    };
  }, []);

  function closeOnLinkClick(event: React.MouseEvent<HTMLElement>): void {
    // Picking the current project redirects to the same page, which keeps the
    // menu mounted, so close it here for every link.
    if (event.target instanceof Element && event.target.closest("a")) {
      if (menuRef.current) menuRef.current.open = false;
    }
  }

  function closeWhenFocusLeaves(
    event: React.FocusEvent<HTMLDetailsElement>,
  ): void {
    // Tab moved past the last item. A click outside is handled above.
    const next = event.relatedTarget;
    if (next instanceof Node && !event.currentTarget.contains(next)) {
      event.currentTarget.open = false;
    }
  }

  return (
    <header className="app-header">
      {/* The key remounts the menu on navigation, so it starts closed on each page. */}
      <details
        key={pathname}
        ref={menuRef}
        className="project-switcher"
        onBlur={closeWhenFocusLeaves}
      >
        <summary aria-label={t.header.switchProject(name)}>
          <span className="dot" data-project={project} aria-hidden="true" />
          {name}
          <svg
            className="chevron"
            aria-hidden="true"
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M6 9l6 6 6-6" />
          </svg>
        </summary>
        <nav
          aria-label={t.header.projectsNav}
          className="project-menu"
          onClick={closeOnLinkClick}
        >
          {PROJECTS.map((item) => (
            <Link
              key={item.key}
              href={localePath(lang, item.path)}
              data-project={item.key}
              aria-current={item.key === project ? "true" : undefined}
            >
              <span className="dot" aria-hidden="true" />
              {t.projects[item.key].name}
            </Link>
          ))}
          <hr />
          <Link href={localePath(lang, "/")} className="all-projects">
            {t.header.allProjects}
          </Link>
        </nav>
      </details>
      <div className="app-header-end">
        {links.length > 0 && (
          <nav aria-label={name} className="app-nav">
            {links.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                aria-current={pathname === link.href ? "page" : undefined}
              >
                {link.label}
              </Link>
            ))}
          </nav>
        )}
        <LanguageLink />
        <ThemeToggle />
        {/* Each app has its own session, so this ends only this app's. */}
        <form
          action={logout.bind(null, lang, project)}
          className="app-header-logout"
        >
          <button type="submit" className="text-button">
            {t.header.logout}
          </button>
        </form>
      </div>
    </header>
  );
}
