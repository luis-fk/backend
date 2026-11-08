"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";
import { PROJECTS, type ProjectKey } from "@/app/projects";

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
  const menuRef = useRef<HTMLDetailsElement>(null);
  const name = PROJECTS.find((item) => item.key === project)?.name ?? project;

  // A <details> only closes from its own summary; close it on Escape or a click outside.
  useEffect(() => {
    function closeMenu(event: PointerEvent | KeyboardEvent): void {
      const menu = menuRef.current;
      if (!menu?.open) return;
      if (event instanceof KeyboardEvent) {
        if (event.key === "Escape") menu.open = false;
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

  return (
    <header className="app-header">
      {/* The key remounts the menu on navigation, so it starts closed on each page. */}
      <details key={pathname} ref={menuRef} className="project-switcher">
        <summary aria-label={`${name}, trocar de projeto`}>
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
        <nav aria-label="Projetos" className="project-menu">
          {PROJECTS.map((item) => (
            <Link
              key={item.key}
              href={item.href}
              data-project={item.key}
              aria-current={item.key === project ? "true" : undefined}
            >
              <span className="dot" aria-hidden="true" />
              {item.name}
            </Link>
          ))}
          <hr />
          <Link href="/" className="all-projects">
            Todos os projetos
          </Link>
        </nav>
      </details>
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
    </header>
  );
}
