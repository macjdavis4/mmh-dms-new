import {
  ArrowLeft,
  Globe,
  Mail,
  MapPin,
  MoreHorizontal,
  Pencil,
  Phone,
  Plus,
  RotateCcw,
  Star,
  Trash2,
  Truck,
  UserRound,
} from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { toast } from "sonner";

import { useCurrentUser } from "@/app/guards";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { SectionCard } from "@/components/form/Field";
import { EmptyState, ErrorState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { StockBadge, UnitPhoto, unitTitle } from "@/features/units/bits";
import { useCustomerUnits } from "@/features/units/api";
import { ApiError } from "@/lib/api";
import { formatNumber } from "@/lib/format";
import type { Address, Contact } from "@/lib/types";

import { useCustomer, useRemoveChild, useRemoveCustomer } from "./api";
import { AddressDialog, ContactDialog } from "./ChildDialogs";
import { CustomerFormDialog } from "./CustomerFormDialog";
import { canEditCustomers, canRemoveCustomers } from "./permissions";

const ADDRESS_KIND: Record<Address["kind"], string> = {
  billing: "Billing",
  shipping: "Shipping",
  site: "Job site",
  other: "Other",
};

function RowMenu({ label, onEdit, onRemove }: { label: string; onEdit: () => void; onRemove: () => void }) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" aria-label={`Actions for ${label}`}>
          <MoreHorizontal className="size-5" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem className="min-h-10" onSelect={onEdit}>
          <Pencil className="size-4" /> Edit
        </DropdownMenuItem>
        <DropdownMenuItem variant="destructive" className="min-h-10" onSelect={onRemove}>
          <Trash2 className="size-4" /> Remove
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export function CustomerDetailPage() {
  const { id = "" } = useParams();
  const user = useCurrentUser();
  const navigate = useNavigate();
  const customer = useCustomer(id);
  const units = useCustomerUnits(id);
  const removeCustomer = useRemoveCustomer();
  const removeContact = useRemoveChild("contacts");
  const removeAddress = useRemoveChild("addresses");
  const [editing, setEditing] = useState(false);
  const [contactDialog, setContactDialog] = useState<Contact | "new" | null>(null);
  const [addressDialog, setAddressDialog] = useState<Address | "new" | null>(null);
  const [confirmRemove, setConfirmRemove] = useState(false);
  const canEdit = canEditCustomers(user.role);

  if (customer.isError) {
    const notFound = customer.error instanceof ApiError && customer.error.status === 404;
    return notFound ? (
      <EmptyState title="Customer not found" message="It may have been removed." action={<Button asChild variant="outline"><Link to="/customers">All customers</Link></Button>} />
    ) : (
      <ErrorState message="Couldn't load this customer." onRetry={() => void customer.refetch()} />
    );
  }
  if (customer.isPending) {
    return (
      <div className="flex flex-col gap-4" role="status" aria-label="Loading">
        <Skeleton className="h-10 w-72" />
        <Skeleton className="h-40" />
        <Skeleton className="h-40" />
      </div>
    );
  }
  const c = customer.data;

  const undoable = (what: string, run: (restore: boolean) => void) => {
    run(false);
    toast.success(`${what} removed`, { action: { label: "Undo", onClick: () => run(true) } });
  };

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link to="/customers" className="text-muted-foreground hover:text-foreground inline-flex min-h-11 items-center gap-1 text-sm font-medium">
          <ArrowLeft className="size-4" /> Customers
        </Link>
        <div className="mt-1 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h1 className="text-2xl font-extrabold tracking-tight sm:text-3xl">{c.name}</h1>
            <div className="text-muted-foreground mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[15px]">
              <Badge variant="outline">{c.kind === "individual" ? "Individual" : "Business"}</Badge>
              {c.account_number && <span>Acct {c.account_number}</span>}
              {c.phone && (
                <a href={`tel:${c.phone}`} className="hover:text-foreground inline-flex items-center gap-1.5">
                  <Phone className="size-4" aria-hidden="true" /> {c.phone}
                </a>
              )}
              {c.email && (
                <a href={`mailto:${c.email}`} className="hover:text-foreground inline-flex items-center gap-1.5">
                  <Mail className="size-4" aria-hidden="true" /> {c.email}
                </a>
              )}
              {c.website && (
                <span className="inline-flex items-center gap-1.5">
                  <Globe className="size-4" aria-hidden="true" /> {c.website}
                </span>
              )}
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {canEdit && (
              <Button variant="outline" onClick={() => setEditing(true)}>
                <Pencil className="size-4" /> Edit
              </Button>
            )}
            {canRemoveCustomers(user.role) && (
              <Button variant="outline" onClick={() => setConfirmRemove(true)}>
                <Trash2 className="size-4" /> Remove
              </Button>
            )}
          </div>
        </div>
        {c.notes && <p className="bg-muted/60 mt-4 rounded-lg border px-4 py-3 text-sm whitespace-pre-line">{c.notes}</p>}
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <SectionCard
          id="contacts"
          title="Contacts"
          actions={
            canEdit && (
              <Button variant="outline" size="sm" onClick={() => setContactDialog("new")}>
                <Plus className="size-4" /> Add contact
              </Button>
            )
          }
        >
          {c.contacts.length === 0 ? (
            <p className="text-muted-foreground text-sm">No contacts yet.</p>
          ) : (
            <ul className="divide-y">
              {c.contacts.map((ct) => (
                <li key={ct.id} className="flex items-start gap-3 py-3 first:pt-0 last:pb-0">
                  <span className="bg-secondary text-secondary-foreground grid size-10 shrink-0 place-items-center rounded-full">
                    <UserRound className="size-5" aria-hidden="true" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="flex flex-wrap items-center gap-2 font-semibold">
                      {ct.full_name}
                      {ct.is_primary && (
                        <Badge variant="outline" className="gap-1">
                          <Star className="size-3" aria-hidden="true" /> Main contact
                        </Badge>
                      )}
                    </p>
                    {ct.title && <p className="text-muted-foreground text-sm">{ct.title}</p>}
                    <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-sm">
                      {ct.phone && <a className="text-primary hover:underline" href={`tel:${ct.phone}`}>{ct.phone}</a>}
                      {ct.mobile && <a className="text-primary hover:underline" href={`tel:${ct.mobile}`}>{ct.mobile} (mobile)</a>}
                      {ct.email && <a className="text-primary hover:underline" href={`mailto:${ct.email}`}>{ct.email}</a>}
                    </div>
                  </div>
                  {canEdit && (
                    <RowMenu
                      label={ct.full_name}
                      onEdit={() => setContactDialog(ct)}
                      onRemove={() =>
                        undoable(ct.full_name, (restore) => removeContact.mutate({ id: ct.id, restore }))
                      }
                    />
                  )}
                </li>
              ))}
            </ul>
          )}
        </SectionCard>

        <SectionCard
          id="addresses"
          title="Addresses"
          actions={
            canEdit && (
              <Button variant="outline" size="sm" onClick={() => setAddressDialog("new")}>
                <Plus className="size-4" /> Add address
              </Button>
            )
          }
        >
          {c.addresses.length === 0 ? (
            <p className="text-muted-foreground text-sm">No addresses yet.</p>
          ) : (
            <ul className="divide-y">
              {c.addresses.map((a) => (
                <li key={a.id} className="flex items-start gap-3 py-3 first:pt-0 last:pb-0">
                  <span className="bg-secondary text-secondary-foreground grid size-10 shrink-0 place-items-center rounded-full">
                    <MapPin className="size-5" aria-hidden="true" />
                  </span>
                  <div className="min-w-0 flex-1 text-sm">
                    <p className="flex flex-wrap items-center gap-2 font-semibold">
                      {a.label || ADDRESS_KIND[a.kind]}
                      {a.is_primary && <Badge variant="outline">Main</Badge>}
                    </p>
                    <p>{a.line1}</p>
                    {a.line2 && <p>{a.line2}</p>}
                    <p>
                      {a.city}, {a.state} {a.postal_code}
                    </p>
                  </div>
                  {canEdit && (
                    <RowMenu
                      label={a.one_line}
                      onEdit={() => setAddressDialog(a)}
                      onRemove={() => undoable("Address", (restore) => removeAddress.mutate({ id: a.id, restore }))}
                    />
                  )}
                </li>
              ))}
            </ul>
          )}
        </SectionCard>
      </div>

      <SectionCard
        id="units"
        title="Their equipment"
        description="Units this customer owns now."
        actions={
          <Button asChild variant="outline" size="sm">
            <Link to={`/units?scope=all&q=${encodeURIComponent(c.name)}`}>
              <Truck className="size-4" /> In inventory
            </Link>
          </Button>
        }
      >
        {units.isPending ? (
          <Skeleton className="h-24" />
        ) : !units.data?.results.length ? (
          <p className="text-muted-foreground text-sm">No units on record for this customer.</p>
        ) : (
          <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {units.data.results.map((u) => (
              <li key={u.id}>
                <Link to={`/units/${u.id}`} className="hover:border-primary/40 flex items-center gap-3 rounded-xl border p-3 transition-colors">
                  <UnitPhoto photoId={u.primary_photo_id} alt={unitTitle(u)} className="size-16 shrink-0 rounded-lg" />
                  <span className="min-w-0">
                    <span className="block truncate font-semibold">{unitTitle(u)}</span>
                    <span className="text-muted-foreground block truncate text-sm">S/N {u.serial_number || "—"}</span>
                    <span className="text-muted-foreground text-xs">{formatNumber(u.current_hours, " h")}</span>
                    <StockBadge status={u.stock_status} />
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </SectionCard>

      {editing && <CustomerFormDialog customer={c} onClose={() => setEditing(false)} />}
      {contactDialog && (
        <ContactDialog
          customerId={c.id}
          {...(contactDialog !== "new" ? { contact: contactDialog } : {})}
          onClose={() => setContactDialog(null)}
        />
      )}
      {addressDialog && (
        <AddressDialog
          customerId={c.id}
          {...(addressDialog !== "new" ? { address: addressDialog } : {})}
          onClose={() => setAddressDialog(null)}
        />
      )}
      <ConfirmDialog
        open={confirmRemove}
        title={`Remove ${c.name}?`}
        description="They'll disappear from lists and search. Their history and units stay on record, and you can restore them."
        confirmLabel="Remove customer"
        onCancel={() => setConfirmRemove(false)}
        onConfirm={() => {
          setConfirmRemove(false);
          removeCustomer.mutate(
            { id: c.id },
            {
              onSuccess: () => {
                toast.success(`${c.name} was removed`, {
                  action: { label: "Undo", onClick: () => removeCustomer.mutate({ id: c.id, restore: true }) },
                });
                void navigate("/customers");
              },
              onError: (e) => toast.error(e instanceof ApiError ? e.message : "Couldn't remove"),
            },
          );
        }}
      />
      {/* Also shown, for completeness, when the customer was removed */}
      {c.is_deleted && (
        <Button variant="outline" onClick={() => removeCustomer.mutate({ id: c.id, restore: true })}>
          <RotateCcw className="size-4" /> Restore customer
        </Button>
      )}
    </div>
  );
}
