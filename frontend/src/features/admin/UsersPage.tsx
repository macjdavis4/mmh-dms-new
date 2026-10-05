import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ColumnDef } from "@tanstack/react-table";
import {
  KeyRound,
  Lock,
  MoreHorizontal,
  Pencil,
  RotateCcw,
  ShieldCheck,
  ShieldOff,
  Trash2,
  UserPlus,
} from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { useCurrentUser } from "@/app/guards";
import { DataTable } from "@/components/DataTable";
import { PageHeader } from "@/components/states";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { initials } from "@/components/shell/UserMenu";
import { useDebounced } from "@/hooks/useDebounced";
import { api, ApiError, type Paginated } from "@/lib/api";
import { formatRelative } from "@/lib/format";
import { type AdminUser, ROLE_LABELS, type Role } from "@/lib/types";

import { UserFormDialog } from "./UserFormDialog";

const ROLE_BADGE: Record<Role, string> = {
  admin: "bg-primary text-primary-foreground",
  sales: "bg-cta/20 text-foreground border-cta/40",
  service: "bg-secondary text-secondary-foreground",
  parts: "bg-secondary text-secondary-foreground",
  read_only: "bg-muted text-muted-foreground",
};

export function RoleBadge({ role }: { role: Role }) {
  return (
    <Badge variant="outline" className={`border font-semibold ${ROLE_BADGE[role]}`}>
      {ROLE_LABELS[role]}
    </Badge>
  );
}

function StatusBadge({ user }: { user: AdminUser }) {
  if (user.is_deleted) return <Badge variant="outline" className="text-muted-foreground">Removed</Badge>;
  if (!user.is_active) return <Badge variant="outline" className="text-warning border-warning/50">Inactive</Badge>;
  return null;
}

function useUsers(params: { q: string; role: string; includeDeleted: boolean }) {
  const q = useDebounced(params.q);
  const search = new URLSearchParams();
  if (q) search.set("q", q);
  if (params.role !== "all") search.set("role", params.role);
  if (params.includeDeleted) search.set("include_deleted", "1");
  search.set("page_size", "200");
  return useQuery({
    queryKey: ["admin", "users", search.toString()],
    queryFn: () => api<Paginated<AdminUser>>(`/api/v1/admin/users?${search.toString()}`),
    placeholderData: keepPreviousData,
  });
}

function errorMessage(err: unknown): string {
  return err instanceof ApiError ? err.message : "Something went wrong.";
}

export function UsersPage() {
  const me = useCurrentUser();
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [role, setRole] = useState("all");
  const [includeDeleted, setIncludeDeleted] = useState(false);
  const [editing, setEditing] = useState<AdminUser | "new" | null>(null);
  const [removing, setRemoving] = useState<AdminUser | null>(null);
  const users = useUsers({ q, role, includeDeleted });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["admin", "users"] });

  const action = useMutation({
    mutationFn: ({ user, op }: { user: AdminUser; op: "restore" | "reset-2fa" | "unlock" | "remove" }) =>
      op === "remove"
        ? api<undefined>(`/api/v1/admin/users/${user.id}`, { method: "DELETE" })
        : api<AdminUser>(`/api/v1/admin/users/${user.id}/${op}`, { method: "POST" }),
    onSuccess: (_data, { user, op }) => {
      void invalidate();
      const name = user.full_name || user.email;
      if (op === "remove") {
        toast.success(`${name} was removed`, {
          description: "They can no longer sign in.",
          action: { label: "Undo", onClick: () => action.mutate({ user, op: "restore" }) },
        });
      } else if (op === "restore") {
        toast.success(`${name} was restored`);
      } else if (op === "reset-2fa") {
        toast.success(`Two-factor reset for ${name}`, { description: "They'll set it up again next time they sign in." });
      } else {
        toast.success(`${name} can sign in again`);
      }
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const columns = useMemo<ColumnDef<AdminUser>[]>(
    () => [
      {
        id: "name",
        header: "Name",
        cell: ({ row }) => {
          const u = row.original;
          return (
            <div className="flex items-center gap-3">
              <Avatar className="size-9">
                <AvatarFallback className="bg-secondary text-secondary-foreground text-xs font-bold">
                  {initials(u)}
                </AvatarFallback>
              </Avatar>
              <div className="min-w-0">
                <p className="truncate font-semibold">{u.full_name || "—"}</p>
                <p className="text-muted-foreground truncate text-sm">{u.email}</p>
              </div>
            </div>
          );
        },
      },
      { id: "role", header: "Role", cell: ({ row }) => <RoleBadge role={row.original.role} /> },
      {
        id: "2fa",
        header: "Two-factor",
        cell: ({ row }) =>
          row.original.two_factor_enabled ? (
            <span className="text-success flex items-center gap-1.5 text-sm font-medium">
              <ShieldCheck className="size-4" aria-hidden="true" /> On
            </span>
          ) : (
            <span className="text-muted-foreground flex items-center gap-1.5 text-sm">
              <ShieldOff className="size-4" aria-hidden="true" /> Off
            </span>
          ),
      },
      {
        id: "last_login",
        header: "Last sign-in",
        cell: ({ row }) => <span className="text-sm">{formatRelative(row.original.last_login)}</span>,
      },
      { id: "status", header: () => <span className="sr-only">Status</span>, cell: ({ row }) => <StatusBadge user={row.original} /> },
      {
        id: "actions",
        header: () => <span className="sr-only">Actions</span>,
        cell: ({ row }) => (
          <RowActions
            user={row.original}
            isSelf={row.original.id === me.id}
            onEdit={() => setEditing(row.original)}
            onRemove={() => setRemoving(row.original)}
            onAction={(op) => action.mutate({ user: row.original, op })}
          />
        ),
      },
    ],
    [me.id, action],
  );

  return (
    <>
      <PageHeader
        title="Users"
        description="Who can sign in and what they can do."
        actions={
          <Button variant="cta" onClick={() => setEditing("new")}>
            <UserPlus className="size-5" /> Add user
          </Button>
        }
      />
      <Card className="gap-0 overflow-hidden py-0">
        <div className="flex flex-col gap-3 border-b p-4 sm:flex-row sm:items-center">
          <div className="flex-1">
            <Label htmlFor="user-search" className="sr-only">
              Search users
            </Label>
            <Input
              id="user-search"
              type="search"
              placeholder="Search by name or email"
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
          </div>
          <div className="flex items-center gap-3">
            <Select value={role} onValueChange={setRole}>
              <SelectTrigger className="h-11 w-40" aria-label="Filter by role">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All roles</SelectItem>
                {(Object.keys(ROLE_LABELS) as Role[]).map((r) => (
                  <SelectItem key={r} value={r}>
                    {ROLE_LABELS[r]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <div className="flex items-center gap-2">
              <Switch id="show-removed" checked={includeDeleted} onCheckedChange={setIncludeDeleted} />
              <Label htmlFor="show-removed" className="text-sm whitespace-nowrap">
                Show removed
              </Label>
            </div>
          </div>
        </div>
        <DataTable
          caption="Users"
          columns={columns}
          data={users.data?.results}
          isLoading={users.isPending}
          error={users.error}
          onRetry={() => void users.refetch()}
          getRowId={(u) => u.id}
          empty={{
            title: q || role !== "all" ? "No users match" : "No users yet",
            message: q || role !== "all" ? "Try a different search or role." : "Add the first staff member.",
          }}
          renderCard={(row) => {
            const u = row.original;
            return (
              <div className="flex items-start gap-3">
                <Avatar className="size-10">
                  <AvatarFallback className="bg-secondary text-secondary-foreground text-xs font-bold">
                    {initials(u)}
                  </AvatarFallback>
                </Avatar>
                <div className="min-w-0 flex-1">
                  <p className="truncate font-semibold">{u.full_name || u.email}</p>
                  <p className="text-muted-foreground truncate text-sm">{u.email}</p>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <RoleBadge role={u.role} />
                    <StatusBadge user={u} />
                    <span className="text-muted-foreground text-xs">
                      {u.two_factor_enabled ? "2FA on" : "2FA off"} · {formatRelative(u.last_login)}
                    </span>
                  </div>
                </div>
                <RowActions
                  user={u}
                  isSelf={u.id === me.id}
                  onEdit={() => setEditing(u)}
                  onRemove={() => setRemoving(u)}
                  onAction={(op) => action.mutate({ user: u, op })}
                />
              </div>
            );
          }}
        />
        {users.data && users.data.results.length > 0 && (
          <p className="text-muted-foreground border-t px-4 py-3 text-sm">
            {users.data.count} {users.data.count === 1 ? "user" : "users"}
          </p>
        )}
      </Card>

      {editing && (
        <UserFormDialog
          user={editing === "new" ? null : editing}
          isSelf={editing !== "new" && editing.id === me.id}
          onClose={() => setEditing(null)}
          onSaved={(saved, created) => {
            void invalidate();
            toast.success(created ? `${saved.full_name || saved.email} was added` : "Changes saved");
            setEditing(null);
          }}
        />
      )}

      <AlertDialog open={removing !== null} onOpenChange={(open) => !open && setRemoving(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove {removing?.full_name || removing?.email}?</AlertDialogTitle>
            <AlertDialogDescription>
              They won't be able to sign in. Their history stays in the system, and you can restore them later.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="h-11">Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90 h-11"
              onClick={() => {
                if (removing) action.mutate({ user: removing, op: "remove" });
                setRemoving(null);
              }}
            >
              Remove user
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

function RowActions({
  user,
  isSelf,
  onEdit,
  onRemove,
  onAction,
}: {
  user: AdminUser;
  isSelf: boolean;
  onEdit: () => void;
  onRemove: () => void;
  onAction: (op: "restore" | "reset-2fa" | "unlock") => void;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" aria-label={`Actions for ${user.full_name || user.email}`}>
          <MoreHorizontal className="size-5" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        {user.is_deleted ? (
          <DropdownMenuItem className="min-h-10" onSelect={() => onAction("restore")}>
            <RotateCcw className="size-4" /> Restore user
          </DropdownMenuItem>
        ) : (
          <>
            <DropdownMenuItem className="min-h-10" onSelect={onEdit}>
              <Pencil className="size-4" /> Edit
            </DropdownMenuItem>
            <DropdownMenuItem className="min-h-10" onSelect={onEdit}>
              <KeyRound className="size-4" /> Set new password
            </DropdownMenuItem>
            <DropdownMenuItem className="min-h-10" onSelect={() => onAction("unlock")}>
              <Lock className="size-4" /> Unlock sign-in
            </DropdownMenuItem>
            {user.two_factor_enabled && !isSelf && (
              <DropdownMenuItem className="min-h-10" onSelect={() => onAction("reset-2fa")}>
                <ShieldOff className="size-4" /> Reset two-factor
              </DropdownMenuItem>
            )}
            {!isSelf && (
              <>
                <DropdownMenuSeparator />
                <DropdownMenuItem variant="destructive" className="min-h-10" onSelect={onRemove}>
                  <Trash2 className="size-4" /> Remove user
                </DropdownMenuItem>
              </>
            )}
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

