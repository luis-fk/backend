import Link from "next/link";
import CornerControls from "@/app/components/CornerControls";
import { commonDictionary } from "@/app/dictionary";
import { localePath, toLocale } from "@/app/i18n";
import { PROJECTS } from "@/app/projects";

export default async function Page({
  params,
}: {
  params: Promise<{ lang: string }>;
}): Promise<React.ReactElement> {
  const lang = toLocale((await params).lang);
  const t = commonDictionary[lang];

  return (
    <main className="home">
      <CornerControls />
      <div className="home-inner">
        <h1 className="home-title">{t.home.title}</h1>
        <nav aria-label={t.home.projectsNav} className="project-grid">
          {PROJECTS.map((project) => (
            <Link
              key={project.key}
              href={localePath(lang, project.path)}
              className="project-link"
              data-project={project.key}
            >
              <span className="project-text">
                <span className="project-name">
                  {t.projects[project.key].name}
                </span>
                <span className="project-description">
                  {t.projects[project.key].description}
                </span>
              </span>
            </Link>
          ))}
        </nav>
      </div>
    </main>
  );
}
