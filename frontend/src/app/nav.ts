import {
  ArrowRightLeft,
  CalendarClock,
  FileUp,
  Gauge,
  KeyRound,
  type LucideIcon,
  Package,
  ScrollText,
  Settings2,
  ShoppingCart,
  Truck,
  UserCog,
  UserRound,
  Users,
  Wrench,
} from "lucide-react";

import type { Role } from "@/lib/types";

export interface NavItem {
  label: string;
  to: string;
  icon: LucideIcon;
  /** Only these roles see the item. Omit for everyone. */
  roles?: Role[];
  /** Set while the section is not built yet; shows a "Soon" tag. */
  comingInPhase?: number;
  /** Feature flag that must be on for the item to show. */
  flag?: string;
  description?: string;
}

export interface NavSection {
  title: string;
  items: NavItem[];
}

export const NAV: NavSection[] = [
  {
    title: "Work",
    items: [
      { label: "Dashboard", to: "/", icon: Gauge },
      {
        label: "Customers",
        to: "/customers",
        icon: Users,
        flag: "customers-units",
        description: "Customers with their contacts, addresses and equipment.",
      },
      {
        label: "Units",
        to: "/units",
        icon: Truck,
        flag: "customers-units",
        description: "Every forklift's full spec card, photos, hours and history, plus stock for sale.",
      },
      {
        label: "Bought and sold",
        to: "/units/changes",
        icon: ArrowRightLeft,
        roles: ["admin", "sales", "read_only"],
        flag: "units-changing-hands",
        description: "Sales, trade-ins, repossessions and buy-backs, each with its own numbers.",
      },
      {
        label: "Service",
        to: "/service",
        icon: Wrench,
        flag: "service",
        description: "Work orders for customer units and our own stock.",
      },
      {
        label: "Maintenance due",
        to: "/service/maintenance",
        icon: CalendarClock,
        flag: "service",
        description: "Planned services that are overdue or due soon.",
      },
      {
        label: "Sales",
        to: "/sales",
        icon: ShoppingCart,
        roles: ["admin", "sales"],
        comingInPhase: 8,
        description: "Quotes, sales and trade-ins.",
      },
      {
        label: "Parts",
        to: "/parts",
        icon: Package,
        comingInPhase: 9,
        description: "Parts catalog, stock levels and invoice receiving.",
      },
      {
        label: "Imports",
        to: "/imports",
        icon: FileUp,
        roles: ["admin", "sales", "service"],
        flag: "batch-import",
        description: "Batch import of the paper unit cards from CSV or the scanning app.",
      },
    ],
  },
  {
    title: "Admin",
    items: [
      { label: "Users", to: "/admin/users", icon: UserRound, roles: ["admin"] },
      { label: "Site settings", to: "/admin/settings", icon: Settings2, roles: ["admin"] },
      { label: "Audit log", to: "/admin/audit", icon: ScrollText, roles: ["admin"] },
      { label: "API keys", to: "/admin/api-keys", icon: KeyRound, roles: ["admin"], flag: "batch-import" },
    ],
  },
  {
    title: "You",
    items: [{ label: "My account", to: "/account", icon: UserCog }],
  },
];

export function navFor(role: Role, flags?: Record<string, boolean>): NavSection[] {
  return NAV.map((section) => ({
    ...section,
    items: section.items.filter(
      (item) => (!item.roles || item.roles.includes(role)) && (!item.flag || (flags?.[item.flag] ?? true)),
    ),
  })).filter((section) => section.items.length > 0);
}

export function findNavItem(path: string): NavItem | undefined {
  return NAV.flatMap((s) => s.items).find((i) => i.to === path);
}

/** The nav item to highlight: the most specific one whose path the page is
 * under ("/service/maintenance" wins over "/service"). */
export function activeNavPath(pathname: string, paths: string[]): string | undefined {
  const matches = paths.filter((p) => (p === "/" ? pathname === "/" : pathname === p || pathname.startsWith(`${p}/`)));
  return matches.sort((a, b) => b.length - a.length)[0];
}
