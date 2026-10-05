"use client";

export default function ErrorPage({ reset }: { error: Error; reset: () => void }) {
  return <main className="page-error"><h1>The studio couldn’t open.</h1><p>Try opening it again.</p><button className="button button-primary" onClick={reset}>Try again</button></main>;
}
