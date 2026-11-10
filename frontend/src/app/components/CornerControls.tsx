import LanguageLink from "@/app/components/LanguageLink";
import ThemeToggle from "@/app/components/ThemeToggle";

// The top right corner of the pages without the app header (the home, the
// login pages and the 404): the language link and the theme switch.
export default function CornerControls(): React.ReactElement {
  return (
    <div className="corner-controls">
      <LanguageLink />
      <ThemeToggle />
    </div>
  );
}
