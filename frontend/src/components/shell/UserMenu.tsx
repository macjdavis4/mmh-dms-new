import { LogOut, ShieldCheck, UserCog } from "lucide-react";
import { useNavigate } from "react-router";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useLogout } from "@/lib/auth";
import type { CurrentUser } from "@/lib/types";

export function initials(user: Pick<CurrentUser, "first_name" | "last_name" | "email">): string {
  const letters = `${user.first_name.charAt(0)}${user.last_name.charAt(0)}`.trim();
  return (letters || user.email.charAt(0)).toUpperCase();
}

export function UserMenu({ user }: { user: CurrentUser }) {
  const logout = useLogout();
  const navigate = useNavigate();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" className="h-11 gap-2 px-1.5 sm:px-2" aria-label="Account menu">
          <Avatar className="size-8">
            <AvatarFallback className="bg-primary text-primary-foreground text-xs font-bold">
              {initials(user)}
            </AvatarFallback>
          </Avatar>
          <span className="hidden max-w-36 truncate text-sm font-semibold xl:inline">
            {user.full_name || user.email}
          </span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-60">
        <DropdownMenuLabel className="flex flex-col">
          <span className="truncate">{user.full_name || user.email}</span>
          <span className="text-muted-foreground truncate text-xs font-normal">
            {user.email} · {user.role_label}
          </span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem className="min-h-10" onSelect={() => void navigate("/account")}>
          <UserCog className="size-4" /> My account
        </DropdownMenuItem>
        <DropdownMenuItem className="min-h-10" onSelect={() => void navigate("/account#security")}>
          <ShieldCheck className="size-4" /> Sign-in security
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          className="min-h-10"
          onSelect={() =>
            logout.mutate(undefined, { onSettled: () => void navigate("/login", { replace: true }) })
          }
        >
          <LogOut className="size-4" /> Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
