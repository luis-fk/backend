import { notFound } from "next/navigation";

// A path that no page matches ends here, so it gets the 404 page in its
// language. It renders on demand: the root layout's dynamicParams = false
// would answer it with Next's default 404 page instead.
export const dynamicParams = true;

export default function UnknownPage(): never {
  notFound();
}
