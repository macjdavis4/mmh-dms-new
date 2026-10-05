import type { ColumnDef } from "@tanstack/react-table";
import { Building2, Plus, Truck, UserRound } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router";

import { useCurrentUser } from "@/app/guards";
import { DataTable } from "@/components/DataTable";
import { PageHeader } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/form/Field";
import type { CustomerRow } from "@/lib/types";

import { useCustomers } from "./api";
import { CustomerFormDialog } from "./CustomerFormDialog";
import { canEditCustomers } from "./permissions";

export function CustomersPage() {
  const user = useCurrentUser();
  const [q, setQ] = useState("");
  const [kind, setKind] = useState("all");
  const [ordering, setOrdering] = useState("name");
  const [adding, setAdding] = useState(false);
  const customers = useCustomers({ q, kind, ordering });

  const columns = useMemo<ColumnDef<CustomerRow>[]>(
    () => [
      {
        id: "name",
        header: "Customer",
        cell: ({ row }) => (
          <Link to={`/customers/${row.original.id}`} className="group flex items-center gap-3">
            <span className="bg-primary/10 text-primary grid size-9 shrink-0 place-items-center rounded-lg dark:bg-primary/15">
              {row.original.kind === "individual" ? <UserRound className="size-4" /> : <Building2 className="size-4" />}
            </span>
            <span className="min-w-0">
              <span className="block truncate font-semibold group-hover:underline">{row.original.name}</span>
              {row.original.account_number && (
                <span className="text-muted-foreground block text-xs">Acct {row.original.account_number}</span>
              )}
            </span>
          </Link>
        ),
      },
      { id: "contact", header: "Main contact", cell: ({ row }) => row.original.primary_contact ?? "—" },
      { id: "phone", header: "Phone", cell: ({ row }) => row.original.phone || "—" },
      { id: "city", header: "Town", cell: ({ row }) => row.original.city ?? "—" },
      {
        id: "units",
        header: "Units",
        cell: ({ row }) => (
          <span className="flex items-center gap-1.5 tabular-nums">
            <Truck className="text-muted-foreground size-4" aria-hidden="true" />
            {row.original.unit_count}
          </span>
        ),
      },
    ],
    [],
  );

  return (
    <>
      <PageHeader
        title="Customers"
        description="Businesses and people we sell to and service."
        actions={
          canEditCustomers(user.role) && (
            <Button variant="cta" onClick={() => setAdding(true)}>
              <Plus className="size-5" /> Add customer
            </Button>
          )
        }
      />
      <Card className="gap-0 overflow-hidden py-0">
        <div className="flex flex-col gap-3 border-b p-4 sm:flex-row sm:items-center">
          <div className="flex-1">
            <Label htmlFor="customer-search" className="sr-only">
              Search customers
            </Label>
            <Input
              id="customer-search"
              type="search"
              placeholder="Search by name, account, phone, contact or town"
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
          </div>
          <div className="flex gap-3">
            <div className="w-36">
              <Label htmlFor="customer-kind" className="sr-only">
                Type
              </Label>
              <NativeSelect
                id="customer-kind"
                value={kind}
                onChange={setKind}
                options={[
                  { value: "all", label: "All types" },
                  { value: "business", label: "Businesses" },
                  { value: "individual", label: "Individuals" },
                ]}
              />
            </div>
            <div className="w-40">
              <Label htmlFor="customer-sort" className="sr-only">
                Sort
              </Label>
              <NativeSelect
                id="customer-sort"
                value={ordering}
                onChange={setOrdering}
                options={[
                  { value: "name", label: "Name A–Z" },
                  { value: "newest", label: "Newest first" },
                  { value: "units", label: "Most units" },
                ]}
              />
            </div>
          </div>
        </div>
        <DataTable
          caption="Customers"
          columns={columns}
          data={customers.data?.results}
          isLoading={customers.isPending}
          error={customers.error}
          onRetry={() => void customers.refetch()}
          getRowId={(c) => c.id}
          empty={{
            title: q ? "No customers match" : "No customers yet",
            message: q ? "Try a different name, phone number or town." : "Add your first customer.",
            action:
              !q && canEditCustomers(user.role) ? (
                <Button variant="cta" onClick={() => setAdding(true)}>
                  <Plus className="size-5" /> Add customer
                </Button>
              ) : undefined,
          }}
          renderCard={(row) => {
            const c = row.original;
            return (
              <Link to={`/customers/${c.id}`} className="flex items-start gap-3">
                <span className="bg-primary/10 text-primary grid size-10 shrink-0 place-items-center rounded-lg">
                  {c.kind === "individual" ? <UserRound className="size-5" /> : <Building2 className="size-5" />}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block font-semibold">{c.name}</span>
                  <span className="text-muted-foreground block text-sm">
                    {[c.primary_contact, c.city].filter(Boolean).join(" · ") || "No contact yet"}
                  </span>
                  <span className="mt-1.5 flex flex-wrap gap-2">
                    {c.phone && <Badge variant="outline">{c.phone}</Badge>}
                    <Badge variant="outline">
                      {c.unit_count} {c.unit_count === 1 ? "unit" : "units"}
                    </Badge>
                  </span>
                </span>
              </Link>
            );
          }}
        />
        {customers.data && customers.data.count > 0 && (
          <p className="text-muted-foreground border-t px-4 py-3 text-sm">
            {customers.data.count} {customers.data.count === 1 ? "customer" : "customers"}
          </p>
        )}
      </Card>
      {adding && <CustomerFormDialog onClose={() => setAdding(false)} />}
    </>
  );
}
