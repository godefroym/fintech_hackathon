import { Link } from "@tanstack/react-router";
import logo from "@/assets/paretokens-logo.png";
import { DisplayUnitToggle } from "@/components/DisplayUnitToggle";

const navLinks = [
  { to: "/", label: "Home", exact: true },
  { to: "/more-statistics", label: "Statistics", exact: false },
  { to: "/recommendations", label: "Recommendations", exact: false },
  { to: "/about", label: "About", exact: false },
] as const;

interface HeaderProps {
  rightSlot?: React.ReactNode;
}

export function Header({ rightSlot }: HeaderProps) {
  return (
    <header className="border-b border-border/60 backdrop-blur-sm">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-6 px-6 py-4">
        <div className="flex items-center gap-4">
          <Link to="/" className="flex items-center gap-3">
            <img
              src={logo}
              alt="Paretokens — turn AI spend into ROI"
              className="h-10 w-auto"
            />
            <span className="hidden font-display text-base font-semibold text-foreground sm:inline">
              Acme Corp
            </span>
          </Link>
        </div>

        <nav className="flex items-center gap-1 sm:gap-2">
          {navLinks.map((link) => (
            <Link
              key={link.to}
              to={link.to}
              activeOptions={{ exact: link.exact }}
              className="rounded-full px-3 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-card hover:text-foreground data-[status=active]:bg-primary/10 data-[status=active]:text-primary"
            >
              {link.label}
            </Link>
          ))}
          <span className="ml-1 hidden sm:inline-flex">
            <DisplayUnitToggle />
          </span>
          {rightSlot}
        </nav>
      </div>
    </header>
  );
}
