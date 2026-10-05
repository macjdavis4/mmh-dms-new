import type { ReactNode } from "react";

import { DealerBadgeSlot, Logo } from "@/components/brand/Logo";
import { ForkliftArt } from "@/components/brand/ForkliftArt";
import { SystemBanner } from "@/components/shell/SystemBanner";
import { ThemeToggle } from "@/components/shell/ThemeToggle";

export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col">
      <SystemBanner />
      <div className="grid flex-1 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
        <section className="bg-sidebar hidden lg:flex lg:flex-col lg:justify-between lg:p-12">
          <Logo inverted />
          <div>
            <ForkliftArt className="text-sidebar-foreground/80 mb-10 w-full max-w-md" />
            <h2 className="max-w-md text-4xl leading-tight font-extrabold text-white">
              Every unit, work order and part. In one place.
            </h2>
            <p className="text-sidebar-muted mt-4 max-w-md text-lg">
              Sales, service and parts for Maine Material Handling.
            </p>
          </div>
          <DealerBadgeSlot className="w-fit" />
        </section>
        <section className="flex flex-col">
          <div className="flex items-center justify-between p-4 sm:p-6">
            <span className="lg:invisible">
              <Logo />
            </span>
            <ThemeToggle />
          </div>
          <div className="flex flex-1 items-start justify-center px-4 pt-6 pb-16 sm:items-center sm:pt-0">
            <div className="w-full max-w-md">{children}</div>
          </div>
        </section>
      </div>
    </div>
  );
}
