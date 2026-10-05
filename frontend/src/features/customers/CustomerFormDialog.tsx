import { Loader2 } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";

import { Field, NativeSelect } from "@/components/form/Field";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { FormError } from "@/features/auth/FormError";
import { ApiError } from "@/lib/api";
import type { Customer } from "@/lib/types";

import { type CustomerInput, useSaveCustomer } from "./api";

export function CustomerFormDialog({ customer, onClose }: { customer?: Customer; onClose: () => void }) {
  const navigate = useNavigate();
  const save = useSaveCustomer(customer?.id);
  const [form, setForm] = useState<CustomerInput>({
    name: customer?.name ?? "",
    kind: customer?.kind ?? "business",
    account_number: customer?.account_number ?? "",
    phone: customer?.phone ?? "",
    email: customer?.email ?? "",
    website: customer?.website ?? "",
    notes: customer?.notes ?? "",
  });
  const [submitted, setSubmitted] = useState(false);
  const server = save.error instanceof ApiError ? save.error : null;
  const nameError = submitted && !form.name.trim() ? "Enter the customer's name." : server?.fieldError("name");
  const set = (key: keyof CustomerInput) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[92dvh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="text-xl font-bold">{customer ? `Edit ${customer.name}` : "Add a customer"}</DialogTitle>
          <DialogDescription>Contacts and addresses can be added on the customer's page.</DialogDescription>
        </DialogHeader>
        <form
          id="customer-form"
          noValidate
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            setSubmitted(true);
            if (!form.name.trim()) return;
            save.mutate(form, {
              onSuccess: (saved) => {
                toast.success(customer ? "Changes saved" : `${saved.name} was added`);
                onClose();
                if (!customer) void navigate(`/customers/${saved.id}`);
              },
            });
          }}
        >
          {server && Object.keys(server.fields).length === 0 && <FormError error={server} />}
          <Field id="c-name" label="Name" error={nameError}>
            <Input id="c-name" value={form.name} onChange={set("name")} aria-invalid={!!nameError} autoComplete="off" />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field id="c-kind" label="Type">
              <NativeSelect
                id="c-kind"
                value={form.kind}
                onChange={(v) => setForm((f) => ({ ...f, kind: v as CustomerInput["kind"] }))}
                options={[
                  { value: "business", label: "Business" },
                  { value: "individual", label: "Individual" },
                ]}
              />
            </Field>
            <Field id="c-acct" label="Account number (optional)" error={server?.fieldError("account_number")}>
              <Input id="c-acct" value={form.account_number} onChange={set("account_number")} autoComplete="off" />
            </Field>
            <Field id="c-phone" label="Phone">
              <Input id="c-phone" type="tel" value={form.phone} onChange={set("phone")} autoComplete="off" />
            </Field>
            <Field id="c-email" label="Email" error={server?.fieldError("email")}>
              <Input id="c-email" type="email" value={form.email} onChange={set("email")} autoComplete="off" />
            </Field>
          </div>
          <Field id="c-web" label="Website">
            <Input id="c-web" value={form.website} onChange={set("website")} autoComplete="off" />
          </Field>
          <Field id="c-notes" label="Notes">
            <Textarea id="c-notes" rows={3} value={form.notes} onChange={set("notes")} />
          </Field>
        </form>
        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="customer-form" variant="cta" disabled={save.isPending}>
            {save.isPending && <Loader2 className="size-4 animate-spin" />}
            {customer ? "Save changes" : "Add customer"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
