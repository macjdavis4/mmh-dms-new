import { useMutation } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useState } from "react";

import { FormError } from "@/features/auth/FormError";
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
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api, ApiError } from "@/lib/api";
import { type AdminUser, ROLE_DESCRIPTIONS, ROLE_LABELS, type Role } from "@/lib/types";

interface FormState {
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  role: Role;
  password: string;
}

export function validateUserForm(form: FormState, isNew: boolean): Partial<Record<keyof FormState, string>> {
  const errors: Partial<Record<keyof FormState, string>> = {};
  if (!form.first_name.trim()) errors.first_name = "Enter a first name.";
  if (!/^\S+@\S+\.\S+$/.test(form.email.trim())) errors.email = "Enter a valid email address.";
  if (isNew && !form.password) errors.password = "Set a starting password.";
  if (form.password && form.password.length < 12) errors.password = "Use at least 12 characters.";
  return errors;
}

function Field({
  id,
  label,
  error,
  hint,
  children,
}: {
  id: string;
  label: string;
  error?: string | undefined;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-2">
      <Label htmlFor={id}>{label}</Label>
      {children}
      {error ? (
        <p id={`${id}-error`} className="text-destructive text-sm">
          {error}
        </p>
      ) : hint ? (
        <p className="text-muted-foreground text-xs">{hint}</p>
      ) : null}
    </div>
  );
}

export function UserFormDialog({
  user,
  isSelf,
  onClose,
  onSaved,
}: {
  user: AdminUser | null;
  isSelf: boolean;
  onClose: () => void;
  onSaved: (user: AdminUser, created: boolean) => void;
}) {
  const isNew = user === null;
  const [form, setForm] = useState<FormState>({
    first_name: user?.first_name ?? "",
    last_name: user?.last_name ?? "",
    email: user?.email ?? "",
    phone: user?.phone ?? "",
    role: user?.role ?? "read_only",
    password: "",
  });
  const [submitted, setSubmitted] = useState(false);

  const save = useMutation({
    mutationFn: (body: Partial<FormState>) =>
      isNew
        ? api<AdminUser>("/api/v1/admin/users", { method: "POST", body })
        : api<AdminUser>(`/api/v1/admin/users/${user.id}`, { method: "PATCH", body }),
    onSuccess: (saved) => onSaved(saved, isNew),
  });

  const clientErrors = submitted ? validateUserForm(form, isNew) : {};
  const serverError = save.error instanceof ApiError ? save.error : null;
  const err = (name: keyof FormState) => clientErrors[name] ?? serverError?.fieldError(name);
  const set = (name: keyof FormState) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [name]: e.target.value }));

  function submit(e: React.SubmitEvent<HTMLFormElement>) {
    e.preventDefault();
    setSubmitted(true);
    if (Object.keys(validateUserForm(form, isNew)).length > 0) return;
    const body: Partial<FormState> = { ...form, email: form.email.trim() };
    if (!form.password) delete body.password;
    save.mutate(body);
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[92dvh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="text-xl font-bold">{isNew ? "Add a user" : `Edit ${user.full_name || user.email}`}</DialogTitle>
          <DialogDescription>
            {isNew
              ? "They'll sign in with this email and the starting password. Admins must also set up two-factor."
              : "Leave the password blank to keep their current one."}
          </DialogDescription>
        </DialogHeader>
        <form id="user-form" onSubmit={submit} noValidate className="flex flex-col gap-4">
          {serverError && Object.keys(serverError.fields).length === 0 && <FormError error={serverError} />}
          <div className="grid gap-4 sm:grid-cols-2">
            <Field id="first_name" label="First name" error={err("first_name")}>
              <Input id="first_name" autoComplete="off" value={form.first_name} onChange={set("first_name")} aria-invalid={!!err("first_name")} />
            </Field>
            <Field id="last_name" label="Last name" error={err("last_name")}>
              <Input id="last_name" autoComplete="off" value={form.last_name} onChange={set("last_name")} />
            </Field>
          </div>
          <Field id="email" label="Email" error={err("email")}>
            <Input id="email" type="email" autoComplete="off" value={form.email} onChange={set("email")} aria-invalid={!!err("email")} />
          </Field>
          <Field id="phone" label="Mobile phone (optional)" error={err("phone")}>
            <Input id="phone" type="tel" autoComplete="off" value={form.phone} onChange={set("phone")} />
          </Field>
          <Field id="role" label="Role" error={err("role")} hint={ROLE_DESCRIPTIONS[form.role]}>
            <Select
              value={form.role}
              onValueChange={(v) => setForm((f) => ({ ...f, role: v as Role }))}
              disabled={isSelf}
            >
              <SelectTrigger id="role" className="h-11 w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {(Object.keys(ROLE_LABELS) as Role[]).map((r) => (
                  <SelectItem key={r} value={r} className="min-h-10">
                    {ROLE_LABELS[r]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
          <Field
            id="password"
            label={isNew ? "Starting password" : "New password"}
            error={err("password")}
            hint="At least 12 characters. Share it with them in person, not by email."
          >
            <Input
              id="password"
              type="password"
              autoComplete="new-password"
              value={form.password}
              onChange={set("password")}
              aria-invalid={!!err("password")}
            />
          </Field>
        </form>
        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="user-form" variant="cta" disabled={save.isPending}>
            {save.isPending && <Loader2 className="size-4 animate-spin" />}
            {isNew ? "Add user" : "Save changes"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
