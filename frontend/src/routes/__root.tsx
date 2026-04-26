import { Outlet, Link, createRootRoute, HeadContent, Scripts } from "@tanstack/react-router";

import appCss from "../styles.css?url";
import { DisplayUnitProvider } from "@/contexts/DisplayUnitContext";

function NotFoundComponent() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="max-w-md text-center">
        <h1 className="text-7xl font-bold text-foreground">404</h1>
        <h2 className="mt-4 text-xl font-semibold text-foreground">Page not found</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          The page you're looking for doesn't exist or has been moved.
        </p>
        <div className="mt-6">
          <Link
            to="/"
            className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            Go home
          </Link>
        </div>
      </div>
    </div>
  );
}

export const Route = createRootRoute({
  head: () => ({
    meta: [
      { charSet: "utf-8" },
      { name: "viewport", content: "width=device-width, initial-scale=1" },
      { title: "Paretokens — AI Spend & ROI Analytics" },
      { name: "description", content: "Visualize employee AI usage, ROI, and token efficiency at a glance." },
      { name: "author", content: "Paretokens" },
      { property: "og:title", content: "Paretokens — AI Spend & ROI Analytics" },
      { property: "og:description", content: "Visualize employee AI usage, ROI, and token efficiency at a glance." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
      { name: "twitter:site", content: "@Paretokens" },
      { name: "twitter:title", content: "Paretokens — AI Spend & ROI Analytics" },
      { name: "twitter:description", content: "Visualize employee AI usage, ROI, and token efficiency at a glance." },
      { property: "og:image", content: "https://pub-bb2e103a32db4e198524a2e9ed8f35b4.r2.dev/b15f1ead-89b7-463b-8dea-d128ee290ce7/id-preview-d04bda17--b0d54e65-da51-48f0-846f-1311a4c0bcad.lovable.app-1777161220990.png" },
      { name: "twitter:image", content: "https://pub-bb2e103a32db4e198524a2e9ed8f35b4.r2.dev/b15f1ead-89b7-463b-8dea-d128ee290ce7/id-preview-d04bda17--b0d54e65-da51-48f0-846f-1311a4c0bcad.lovable.app-1777161220990.png" },
    ],
    links: [
      { rel: "preconnect", href: "https://fonts.googleapis.com" },
      { rel: "preconnect", href: "https://fonts.gstatic.com", crossOrigin: "anonymous" },
      {
        rel: "stylesheet",
        href: "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Space+Grotesk:wght@500;600;700&display=swap",
      },
      {
        rel: "stylesheet",
        href: appCss,
      },
    ],
  }),
  shellComponent: RootShell,
  component: RootComponent,
  notFoundComponent: NotFoundComponent,
});

function RootShell({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <HeadContent />
      </head>
      <body>
        {children}
        <Scripts />
      </body>
    </html>
  );
}

function RootComponent() {
  return (
    <DisplayUnitProvider>
      <Outlet />
    </DisplayUnitProvider>
  );
}
