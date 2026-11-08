import Link from "next/link";
import { PROJECTS } from "@/app/projects";

export default function Page(): React.ReactElement {
  return (
    <main className="home">
      <div className="home-inner">
        <h1 className="home-title">Projetos</h1>
        <nav aria-label="Projetos" className="project-grid">
          {PROJECTS.map((project) => (
            <Link
              key={project.key}
              href={project.href}
              className="project-link"
              data-project={project.key}
            >
              <span className="project-text">
                <span className="project-name">{project.name}</span>
                <span className="project-description">
                  {project.description}
                </span>
              </span>
            </Link>
          ))}
        </nav>
      </div>
    </main>
  );
}
