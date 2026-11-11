"use client";

// A script the browser runs while it parses the server's HTML, before the first
// paint. React never runs a script it adds in the browser, and warns about one,
// which happens when it renders the root layout again there (switching language
// remounts it). So in the browser the script is plain text, as in Next's guide
// "Preventing flash before hydration", and suppressHydrationWarning accepts the
// type that differs from the server's. It is a Client Component so that the
// browser renders it with its own type.
export default function InlineScript({
  html,
}: Readonly<{ html: string }>): React.ReactElement {
  return (
    <script
      type={typeof window === "undefined" ? "text/javascript" : "text/plain"}
      suppressHydrationWarning
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
