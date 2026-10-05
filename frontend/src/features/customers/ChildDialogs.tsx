import { Loader2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Field, NativeSelect } from "@/components/form/Field";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/form/Checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { FormError } from "@/features/auth/FormError";
import { ApiError } from "@/lib/api";
import type { Address, Contact } from "@/lib/types";

import { useSaveChild } from "./api";

function Shell({
  title,
  formId,
  pending,
  onClose,
  children,
}: {
  title: string;
  formId: string;
  pending: boolean;
  onClose: () => void;
  children: React.ReactNode;
}) {
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[92dvh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="text-xl font-bold">{title}</DialogTitle>
          <DialogDescription className="sr-only">{title}</DialogDescription>
        </DialogHeader>
        {children}
        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form={formId} variant="cta" disabled={pending}>
            {pending && <Loader2 className="size-4 animate-spin" />} Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function ContactDialog({
  customerId,
  contact,
  onClose,
}: {
  customerId: string;
  contact?: Contact;
  onClose: () => void;
}) {
  const save = useSaveChild<Contact>("contacts", customerId);
  const [form, setForm] = useState({
    first_name: contact?.first_name ?? "",
    last_name: contact?.last_name ?? "",
    title: contact?.title ?? "",
    phone: contact?.phone ?? "",
    mobile: contact?.mobile ?? "",
    email: contact?.email ?? "",
    is_primary: contact?.is_primary ?? false,
  });
  const [submitted, setSubmitted] = useState(false);
  const server = save.error instanceof ApiError ? save.error : null;
  const nameError =
    submitted && !form.first_name.trim() && !form.last_name.trim()
      ? "Enter a first or last name."
      : server?.fieldError("first_name");
  const set = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));

  return (
    <Shell title={contact ? "Edit contact" : "Add a contact"} formId="contact-form" pending={save.isPending} onClose={onClose}>
      <form
        id="contact-form"
        noValidate
        className="flex flex-col gap-4"
        onSubmit={(e) => {
          e.preventDefault();
          setSubmitted(true);
          if (!form.first_name.trim() && !form.last_name.trim()) return;
          save.mutate(
            { id: contact?.id, body: form },
            {
              onSuccess: () => {
                toast.success(contact ? "Contact saved" : "Contact added");
                onClose();
              },
            },
          );
        }}
      >
        {server && Object.keys(server.fields).length === 0 && <FormError error={server} />}
        <div className="grid gap-4 sm:grid-cols-2">
          <Field id="ct-first" label="First name" error={nameError}>
            <Input id="ct-first" value={form.first_name} onChange={set("first_name")} aria-invalid={!!nameError} />
          </Field>
          <Field id="ct-last" label="Last name">
            <Input id="ct-last" value={form.last_name} onChange={set("last_name")} />
          </Field>
        </div>
        <Field id="ct-title" label="Job title">
          <Input id="ct-title" value={form.title} onChange={set("title")} placeholder="e.g. Maintenance lead" />
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field id="ct-phone" label="Phone">
            <Input id="ct-phone" type="tel" value={form.phone} onChange={set("phone")} />
          </Field>
          <Field id="ct-mobile" label="Mobile">
            <Input id="ct-mobile" type="tel" value={form.mobile} onChange={set("mobile")} />
          </Field>
        </div>
        <Field id="ct-email" label="Email" error={server?.fieldError("email")}>
          <Input id="ct-email" type="email" value={form.email} onChange={set("email")} />
        </Field>
        <Checkbox
          id="ct-primary"
          checked={form.is_primary}
          onChange={(v) => setForm((f) => ({ ...f, is_primary: v }))}
          label="Main contact for this customer"
        />
      </form>
    </Shell>
  );
}

const ADDRESS_KINDS = [
  { value: "billing", label: "Billing" },
  { value: "shipping", label: "Shipping" },
  { value: "site", label: "Job site" },
  { value: "other", label: "Other" },
];

export function AddressDialog({
  customerId,
  address,
  onClose,
}: {
  customerId: string;
  address?: Address;
  onClose: () => void;
}) {
  const save = useSaveChild<Address>("addresses", customerId);
  const [form, setForm] = useState({
    kind: address?.kind ?? "billing",
    label: address?.label ?? "",
    line1: address?.line1 ?? "",
    line2: address?.line2 ?? "",
    city: address?.city ?? "",
    state: address?.state ?? "ME",
    postal_code: address?.postal_code ?? "",
    is_primary: address?.is_primary ?? false,
  });
  const [submitted, setSubmitted] = useState(false);
  const server = save.error instanceof ApiError ? save.error : null;
  const err = (k: "line1" | "city") =>
    submitted && !form[k].trim() ? (k === "line1" ? "Enter the street address." : "Enter the town.") : server?.fieldError(k);
  const set = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));

  return (
    <Shell title={address ? "Edit address" : "Add an address"} formId="address-form" pending={save.isPending} onClose={onClose}>
      <form
        id="address-form"
        noValidate
        className="flex flex-col gap-4"
        onSubmit={(e) => {
          e.preventDefault();
          setSubmitted(true);
          if (!form.line1.trim() || !form.city.trim()) return;
          save.mutate(
            { id: address?.id, body: form },
            {
              onSuccess: () => {
                toast.success(address ? "Address saved" : "Address added");
                onClose();
              },
            },
          );
        }}
      >
        {server && Object.keys(server.fields).length === 0 && <FormError error={server} />}
        <div className="grid gap-4 sm:grid-cols-2">
          <Field id="ad-kind" label="Type">
            <NativeSelect
              id="ad-kind"
              value={form.kind}
              onChange={(v) => setForm((f) => ({ ...f, kind: v as Address["kind"] }))}
              options={ADDRESS_KINDS}
            />
          </Field>
          <Field id="ad-label" label="Label (optional)">
            <Input id="ad-label" value={form.label} onChange={set("label")} placeholder="e.g. Main plant" />
          </Field>
        </div>
        <Field id="ad-line1" label="Street address" error={err("line1")}>
          <Input id="ad-line1" value={form.line1} onChange={set("line1")} aria-invalid={!!err("line1")} />
        </Field>
        <Field id="ad-line2" label="Address line 2">
          <Input id="ad-line2" value={form.line2} onChange={set("line2")} />
        </Field>
        <div className="grid grid-cols-[1fr_5rem_7rem] gap-3">
          <Field id="ad-city" label="Town" error={err("city")}>
            <Input id="ad-city" value={form.city} onChange={set("city")} aria-invalid={!!err("city")} />
          </Field>
          <Field id="ad-state" label="State">
            <Input id="ad-state" value={form.state} onChange={set("state")} maxLength={40} />
          </Field>
          <Field id="ad-zip" label="ZIP">
            <Input id="ad-zip" inputMode="numeric" value={form.postal_code} onChange={set("postal_code")} />
          </Field>
        </div>
        <Checkbox
          id="ad-primary"
          checked={form.is_primary}
          onChange={(v) => setForm((f) => ({ ...f, is_primary: v }))}
          label="Main address for this customer"
        />
      </form>
    </Shell>
  );
}
