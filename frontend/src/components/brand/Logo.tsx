import { cn } from "@/lib/utils";

/**
 * Maine Material Handling mark: a placeholder monogram until the final
 * company logo file is supplied (drop it into src/components/brand/).
 */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" className={cn("size-9 shrink-0", className)} aria-hidden="true">
      <rect width="40" height="40" rx="9" fill="#0B2A4A" />
      <rect x="0.75" y="0.75" width="38.5" height="38.5" rx="8.25" fill="none" stroke="#ffffff" strokeOpacity="0.18" />
      <path d="M11.5 26V9h4.2l4.3 8.2 4.3-8.2h4.2v17h-3.8V15.6l-3.6 6.7h-2.2l-3.6-6.7V26z" fill="#ffffff" />
      {/* amber fork tines */}
      <rect x="9" y="29.5" width="22" height="3.5" rx="1.2" fill="#FFB000" />
    </svg>
  );
}

export function Logo({ inverted = false, compact = false }: { inverted?: boolean; compact?: boolean }) {
  return (
    <span className="flex items-center gap-2.5">
      <LogoMark />
      {!compact && (
        <span className="flex flex-col leading-none">
          <span
            className={cn(
              "text-[15px] font-extrabold tracking-tight",
              inverted ? "text-white" : "text-primary dark:text-foreground",
            )}
          >
            Maine Material Handling
          </span>
          <span
            className={cn(
              "mt-1 text-[11px] font-semibold tracking-[0.18em] uppercase",
              inverted ? "text-sidebar-muted" : "text-muted-foreground",
            )}
          >
            Dealer Management
          </span>
        </span>
      )}
    </span>
  );
}

/**
 * Slot for the "Authorized Hyundai Dealer" badge. The official badge artwork
 * must come from the manufacturer's dealer program; until it is supplied this
 * renders a neutral text placeholder (no trademarks or logos).
 */
export function DealerBadgeSlot({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "border-sidebar-border text-sidebar-muted flex items-center justify-center rounded-lg border border-dashed px-3 py-2 text-center text-[11px] font-semibold tracking-wide uppercase",
        className,
      )}
      data-slot="dealer-badge"
    >
      Authorized Hyundai Dealer
    </div>
  );
}
