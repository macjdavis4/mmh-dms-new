import { Menu } from "lucide-react";
import { useState } from "react";
import { Link, Outlet } from "react-router";

import { DealerBadgeSlot, Logo } from "@/components/brand/Logo";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet";
import type { CurrentUser } from "@/lib/types";

import { GlobalSearch, MobileSearchButton } from "./GlobalSearch";
import { SidebarNav } from "./SidebarNav";
import { EnvironmentTag, SystemBanner } from "./SystemBanner";
import { ThemeToggle } from "./ThemeToggle";
import { UserMenu } from "./UserMenu";

function SidebarBody({ user, onNavigate }: { user: CurrentUser; onNavigate?: () => void }) {
  return (
    <div className="flex h-full flex-col">
      <div className="flex h-16 shrink-0 items-center px-5">
        <Link to="/" onClick={onNavigate} className="rounded-md focus-visible:ring-2 focus-visible:ring-[var(--cta)] focus-visible:outline-none">
          <Logo inverted />
        </Link>
      </div>
      <div className="flex-1 overflow-y-auto px-3 py-4">
        <SidebarNav role={user.role} {...(onNavigate ? { onNavigate } : {})} />
      </div>
      <div className="border-sidebar-border border-t p-4">
        <DealerBadgeSlot />
      </div>
    </div>
  );
}

export function AppShell({ user }: { user: CurrentUser }) {
  const [menuOpen, setMenuOpen] = useState(false);
  return (
    <div className="min-h-dvh">
      <a
        href="#main"
        className="bg-cta text-cta-foreground sr-only z-[60] rounded-md px-4 py-2 font-semibold focus:not-sr-only focus:fixed focus:top-2 focus:left-2"
      >
        Skip to content
      </a>

      {/* Desktop and landscape tablet: fixed sidebar */}
      <aside className="bg-sidebar text-sidebar-foreground border-sidebar-border fixed inset-y-0 left-0 z-30 hidden w-64 border-r lg:block">
        <SidebarBody user={user} />
      </aside>

      {/* Phone and portrait tablet: slide-out menu */}
      <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
        <SheetContent side="left" className="bg-sidebar text-sidebar-foreground w-72 border-none p-0 [&>button]:text-white">
          <SheetTitle className="sr-only">Menu</SheetTitle>
          <SheetDescription className="sr-only">Main navigation</SheetDescription>
          <SidebarBody user={user} onNavigate={() => setMenuOpen(false)} />
        </SheetContent>
      </Sheet>

      <div className="flex min-h-dvh flex-col lg:pl-64">
        <SystemBanner />
        <header className="bg-card/95 supports-[backdrop-filter]:bg-card/85 sticky top-0 z-20 border-b backdrop-blur">
          <div className="flex h-16 items-center gap-2 px-3 sm:px-5 lg:gap-4 lg:px-8">
            <Button
              variant="ghost"
              size="icon"
              className="size-11 lg:hidden"
              onClick={() => setMenuOpen(true)}
              aria-label="Open menu"
            >
              <Menu className="size-6" />
            </Button>
            <Link to="/" className="mr-1 lg:hidden" aria-label="Dashboard">
              <span className="sm:hidden">
                <Logo compact />
              </span>
              <span className="hidden sm:inline md:hidden">
                <Logo />
              </span>
            </Link>
            <div className="hidden flex-1 md:flex">
              <GlobalSearch />
            </div>
            <div className="ml-auto flex items-center gap-1 sm:gap-2">
              <EnvironmentTag />
              <span className="md:hidden">
                <MobileSearchButton />
              </span>
              <ThemeToggle />
              <UserMenu user={user} />
            </div>
          </div>
        </header>
        <main id="main" tabIndex={-1} className="flex-1 px-4 py-6 outline-none sm:px-6 lg:px-8 lg:py-8">
          <div className="mx-auto w-full max-w-7xl">
            <Outlet />
          </div>
        </main>
        <footer className="text-muted-foreground px-4 pb-6 text-center text-xs sm:px-6 lg:px-8">
          Maine Material Handling · Bangor, Maine
        </footer>
      </div>
    </div>
  );
}
