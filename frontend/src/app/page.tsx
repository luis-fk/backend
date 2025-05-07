import Link from "next/link";
import "@/app/main-page.css";

export default function Page() {
  return (
    <div className="linksContainer">
      <Link href="/political-culture" className="button">
        Political Culture
      </Link>
      <Link href="/plants" className="button">
        Plants
      </Link>
    </div>
  );
}
