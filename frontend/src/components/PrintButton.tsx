import { ChevronDown, Printer } from "lucide-react";

import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";

/** Opens a PDF in a new tab (the browser's viewer prints or saves it). */
export function PrintButton({ href, label = "Print" }: { href: string; label?: string }) {
  return (
    <Button asChild variant="outline">
      <a href={href} target="_blank" rel="noreferrer">
        <Printer className="size-4" /> {label}
      </a>
    </Button>
  );
}

/** Several printouts behind one button, e.g. a spec sheet with or without the price. */
export function PrintMenu({ label, items }: { label: string; items: { label: string; href: string }[] }) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline">
          <Printer className="size-4" /> {label} <ChevronDown className="size-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {items.map((item) => (
          <DropdownMenuItem key={item.href} asChild className="min-h-10">
            <a href={item.href} target="_blank" rel="noreferrer">
              {item.label}
            </a>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
