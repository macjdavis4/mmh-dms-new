import { NavLink } from "react-router";

import { navFor } from "@/app/nav";
import { useFlags } from "@/lib/flags";
import type { Role } from "@/lib/types";
import { cn } from "@/lib/utils";

export function SidebarNav({ role, onNavigate }: { role: Role; onNavigate?: () => void }) {
  const { data } = useFlags();
  return (
    <nav aria-label="Main" className="flex flex-col gap-6">
      {navFor(role, data?.flags).map((section) => (
        <div key={section.title}>
          <p className="text-sidebar-muted mb-2 px-3 text-[11px] font-semibold tracking-[0.16em] uppercase">
            {section.title}
          </p>
          <ul className="flex flex-col gap-0.5">
            {section.items.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  end={item.to === "/"}
                  onClick={onNavigate}
                  className={({ isActive }) =>
                    cn(
                      "group flex min-h-11 items-center gap-3 rounded-lg px-3 text-[15px] font-medium transition-colors",
                      "focus-visible:ring-cta focus-visible:ring-2 focus-visible:outline-none",
                      isActive
                        ? "bg-sidebar-active text-white shadow-[inset_3px_0_0_var(--cta)]"
                        : "text-sidebar-foreground hover:bg-sidebar-active/60 hover:text-white",
                    )
                  }
                >
                  <item.icon className="size-[18px] shrink-0 opacity-90" aria-hidden="true" />
                  <span className="flex-1 truncate">{item.label}</span>
                  {item.comingInPhase !== undefined && (
                    <span className="text-sidebar-muted border-sidebar-border rounded-full border px-2 py-0.5 text-[10px] font-semibold tracking-wide uppercase">
                      Soon
                    </span>
                  )}
                </NavLink>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </nav>
  );
}
