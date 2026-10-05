import { ArrowLeft, Loader2, Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";
import { toast } from "sonner";

import { useCurrentUser } from "@/app/guards";
import { Field } from "@/components/form/Field";
import { EmptyState, ErrorState, PageHeader } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { FormError } from "@/features/auth/FormError";
import { ApiError } from "@/lib/api";
import type { PartBin } from "@/lib/types";

import { canEditParts, useBinAction, useBins, useSaveBin } from "./api";

function BinDialog({ bin, onClose }: { bin: PartBin | null; onClose: () => void }) {
  const save = useSaveBin(bin?.id);
  const [code, setCode] = useState(bin?.code ?? "");
  const [description, setDescription] = useState(bin?.description ?? "");
  const err = save.error instanceof ApiError ? save.error : null;
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="text-xl font-bold">{bin ? `Edit bin ${bin.code}` : "Add a bin"}</DialogTitle>
          <DialogDescription>A shelf location in the parts room, like A-03-2 (aisle, shelf, level).</DialogDescription>
        </DialogHeader>
        <form
          id="bin-form"
          noValidate
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            save.mutate(
              { code, description },
              {
                onSuccess: (b) => {
                  toast.success(`Bin ${b.code} saved`);
                  onClose();
                },
              },
            );
          }}
        >
          {err && Object.keys(err.fields).length === 0 && <FormError error={err} />}
          <Field id="bin-code" label="Code" error={err?.fieldError("code")}>
            <Input id="bin-code" className="font-mono uppercase" value={code} maxLength={30} onChange={(e) => setCode(e.target.value)} />
          </Field>
          <Field id="bin-desc" label="What's there (optional)">
            <Input id="bin-desc" value={description} maxLength={200} onChange={(e) => setDescription(e.target.value)} />
          </Field>
        </form>
        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="bin-form" variant="cta" disabled={!code.trim() || save.isPending}>
            {save.isPending && <Loader2 className="size-4 animate-spin" />} Save bin
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function BinsPage() {
  const user = useCurrentUser();
  const bins = useBins();
  const remove = useBinAction();
  const [editing, setEditing] = useState<PartBin | "new" | null>(null);
  const canEdit = canEditParts(user.role);

  return (
    <>
      <Link to="/parts" className="text-muted-foreground hover:text-foreground inline-flex min-h-11 items-center gap-1 text-sm font-medium">
        <ArrowLeft className="size-4" /> Parts
      </Link>
      <PageHeader
        title="Bins"
        description="Where parts live on the shelves."
        actions={
          canEdit && (
            <Button variant="cta" onClick={() => setEditing("new")}>
              <Plus className="size-5" /> Add bin
            </Button>
          )
        }
      />
      <Card className="gap-0 overflow-hidden py-0">
        {bins.isPending ? (
          <div className="flex flex-col gap-3 p-4" role="status" aria-live="polite">
            <span className="sr-only">Loading</span>
            {Array.from({ length: 4 }, (_, i) => (
              <Skeleton key={i} className="h-12" />
            ))}
          </div>
        ) : bins.isError ? (
          <ErrorState message="We couldn't load the bins." onRetry={() => void bins.refetch()} />
        ) : bins.data.length === 0 ? (
          <EmptyState title="No bins yet" message="Add the shelf locations in the parts room." />
        ) : (
          <ul className="divide-y" aria-label="Bins">
            {bins.data.map((b) => (
              <li key={b.id} className="flex items-center gap-3 px-4 py-3">
                <span className="bg-muted grid h-11 min-w-20 place-items-center rounded-lg px-2 font-mono font-bold">{b.code}</span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate">{b.description || <span className="text-muted-foreground">No description</span>}</span>
                  <Link to={`/parts?bin=${b.id}`} className="text-primary text-sm hover:underline">
                    {b.part_count} {b.part_count === 1 ? "part" : "parts"}
                  </Link>
                </span>
                {canEdit && (
                  <>
                    <Button variant="ghost" size="icon" aria-label={`Edit bin ${b.code}`} onClick={() => setEditing(b)}>
                      <Pencil className="size-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={`Remove bin ${b.code}`}
                      onClick={() =>
                        remove.mutate(
                          { id: b.id },
                          {
                            onSuccess: () => toast.success(`Bin ${b.code} removed`, { action: { label: "Undo", onClick: () => remove.mutate({ id: b.id, restore: true }) } }),
                            onError: (e) => toast.error(e instanceof ApiError ? (e.fieldError("code") ?? e.message) : "Couldn't remove it."),
                          },
                        )
                      }
                    >
                      <Trash2 className="size-4" />
                    </Button>
                  </>
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>
      {editing && <BinDialog bin={editing === "new" ? null : editing} onClose={() => setEditing(null)} />}
    </>
  );
}
