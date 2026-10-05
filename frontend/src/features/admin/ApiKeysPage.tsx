import type { ColumnDef } from "@tanstack/react-table";
import { Check, Copy, KeyRound, Loader2, Plus } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { ConfirmDialog } from "@/components/ConfirmDialog";
import { DataTable } from "@/components/DataTable";
import { Field } from "@/components/form/Field";
import { PageHeader } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { useCreateApiKey, useApiKeys, useRevokeApiKey } from "@/features/imports/api";
import { ApiError } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { ApiKey } from "@/lib/types";

function KeyStatus({ apiKey }: { apiKey: ApiKey }) {
  return apiKey.is_active ? (
    <Badge variant="outline" className="bg-success/15 text-success border-success/30 font-semibold">
      Active
    </Badge>
  ) : (
    <Badge variant="outline" className="text-muted-foreground font-semibold">
      Revoked
    </Badge>
  );
}

function NewKeyDialog({ onClose }: { onClose: () => void }) {
  const [name, setName] = useState("");
  const [copied, setCopied] = useState(false);
  const create = useCreateApiKey();
  const created = create.data;
  const error = create.error instanceof ApiError ? (create.error.fieldError("name") ?? create.error.message) : undefined;

  async function copy(text: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      toast.success("Key copied");
    } catch {
      toast.error("Couldn't copy. Select the key and copy it by hand.");
    }
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-lg">
        {created?.key ? (
          <>
            <DialogHeader>
              <DialogTitle className="text-xl font-bold">Copy the key now</DialogTitle>
              <DialogDescription>
                This is the only time it's shown. Paste it into the scanning app's settings. If it's lost, revoke it and make a new one.
              </DialogDescription>
            </DialogHeader>
            <div className="bg-muted flex items-center gap-2 rounded-lg p-3">
              <code className="min-w-0 flex-1 font-mono text-sm break-all select-all" data-testid="new-api-key">
                {created.key}
              </code>
              <Button variant="outline" size="icon" aria-label="Copy key" onClick={() => void copy(created.key ?? "")}>
                {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
              </Button>
            </div>
            <DialogFooter>
              <Button variant="cta" onClick={onClose}>
                Done
              </Button>
            </DialogFooter>
          </>
        ) : (
          <form
            id="api-key-form"
            onSubmit={(e) => {
              e.preventDefault();
              create.mutate(name);
            }}
            className="flex flex-col gap-4"
          >
            <DialogHeader>
              <DialogTitle className="text-xl font-bold">New API key</DialogTitle>
              <DialogDescription>Imports sent with this key are recorded as you.</DialogDescription>
            </DialogHeader>
            <Field id="key-name" label="Name" error={error} hint="Where it's used, e.g. “Card scanner tablet”.">
              <Input id="key-name" value={name} onChange={(e) => setName(e.target.value)} autoComplete="off" aria-invalid={!!error || undefined} />
            </Field>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={onClose}>
                Cancel
              </Button>
              <Button type="submit" variant="cta" disabled={create.isPending}>
                {create.isPending && <Loader2 className="size-4 animate-spin" />} Create key
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}

export function ApiKeysPage() {
  const keys = useApiKeys();
  const revoke = useRevokeApiKey();
  const [creating, setCreating] = useState(false);
  const [revoking, setRevoking] = useState<ApiKey | null>(null);

  const columns = useMemo<ColumnDef<ApiKey>[]>(
    () => [
      {
        id: "name",
        header: "Name",
        cell: ({ row }) => (
          <span>
            <span className="block font-semibold">{row.original.name}</span>
            <code className="text-muted-foreground text-xs">{row.original.prefix}…</code>
          </span>
        ),
      },
      { id: "created", header: "Created", cell: ({ row }) => `${formatDateTime(row.original.created_at)} · ${row.original.created_by_name}` },
      { id: "used", header: "Last used", cell: ({ row }) => (row.original.last_used_at ? formatDateTime(row.original.last_used_at) : "Never") },
      { id: "status", header: "Status", cell: ({ row }) => <KeyStatus apiKey={row.original} /> },
      {
        id: "actions",
        header: "",
        cell: ({ row }) =>
          row.original.is_active && (
            <Button variant="outline" size="sm" onClick={() => setRevoking(row.original)}>
              Revoke
            </Button>
          ),
      },
    ],
    [],
  );

  return (
    <>
      <PageHeader
        title="API keys"
        description="For the card-scanning app and other tools that send unit cards to the import API."
        actions={
          <Button variant="cta" onClick={() => setCreating(true)}>
            <Plus className="size-5" /> New key
          </Button>
        }
      />
      <Card className="gap-0 overflow-hidden py-0">
        <DataTable
          caption="API keys"
          columns={columns}
          data={keys.data}
          isLoading={keys.isPending}
          error={keys.error}
          onRetry={() => void keys.refetch()}
          getRowId={(k) => k.id}
          renderCard={(row) => (
            <div className="flex flex-col gap-2 p-4">
              <span className="flex items-center justify-between gap-3">
                <span className="font-semibold">{row.original.name}</span>
                <KeyStatus apiKey={row.original} />
              </span>
              <span className="text-muted-foreground text-sm">
                <code>{row.original.prefix}…</code> · last used {row.original.last_used_at ? formatDateTime(row.original.last_used_at) : "never"}
              </span>
              {row.original.is_active && (
                <Button variant="outline" size="sm" className="self-start" onClick={() => setRevoking(row.original)}>
                  Revoke
                </Button>
              )}
            </div>
          )}
          empty={{
            title: "No API keys",
            message: "Only needed once the scanning app is set up. Spreadsheet imports don't need a key.",
          }}
        />
      </Card>
      <Card className="mt-6 gap-2 p-5 text-sm">
        <h2 className="flex items-center gap-2 font-bold">
          <KeyRound className="size-4" aria-hidden="true" /> For the developer of the scanning app
        </h2>
        <p className="text-muted-foreground">
          Send unit cards as JSON to <code className="bg-muted rounded px-1">POST /api/v1/import/v1/units</code> with the header{" "}
          <code className="bg-muted rounded px-1">Authorization: Api-Key …</code>. The format is described in{" "}
          <a className="text-primary font-medium hover:underline" href="/api/v1/import/v1/schema.json" target="_blank" rel="noreferrer">
            the JSON Schema
          </a>{" "}
          and in docs/IMPORT_FORMAT.md. Limit: 30 requests a minute per key.
        </p>
      </Card>
      {creating && <NewKeyDialog onClose={() => setCreating(false)} />}
      <ConfirmDialog
        open={revoking !== null}
        title={`Revoke “${revoking?.name ?? ""}”?`}
        description="Anything using this key stops working straight away. This can't be undone; make a new key instead."
        confirmLabel="Revoke key"
        onCancel={() => setRevoking(null)}
        onConfirm={() => {
          if (revoking) revoke.mutate(revoking.id, { onSuccess: () => toast.success("Key revoked") });
          setRevoking(null);
        }}
      />
    </>
  );
}
