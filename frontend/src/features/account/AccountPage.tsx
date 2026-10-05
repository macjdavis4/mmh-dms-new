import { useMutation, useQueryClient } from "@tanstack/react-query";
import { KeyRound, Loader2, ShieldCheck, ShieldOff, UserRound } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { PageHeader } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
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
import { FormError } from "@/features/auth/FormError";
import { RecoveryCodes, TwoFactorSetupFlow } from "@/features/auth/TwoFactorSetupPage";
import { api, ApiError } from "@/lib/api";
import { meKey, useMe } from "@/lib/auth";
import type { Me } from "@/lib/types";

function PasswordCard() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const change = useMutation({
    mutationFn: () =>
      api<undefined>("/api/v1/auth/password", {
        method: "POST",
        body: { current_password: current, new_password: next },
      }),
    onSuccess: () => {
      toast.success("Password changed");
      setCurrent("");
      setNext("");
      setConfirm("");
      setSubmitted(false);
    },
  });
  const server = change.error instanceof ApiError ? change.error : null;
  const tooShort = submitted && next.length > 0 && next.length < 12;
  const mismatch = submitted && confirm !== next;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <KeyRound className="size-5" aria-hidden="true" /> Password
        </CardTitle>
        <CardDescription>Use at least 12 characters. A short sentence is easy to remember.</CardDescription>
      </CardHeader>
      <CardContent>
        <form
          className="flex flex-col gap-4"
          noValidate
          onSubmit={(e) => {
            e.preventDefault();
            setSubmitted(true);
            if (!current || next.length < 12 || next !== confirm) return;
            change.mutate();
          }}
        >
          {server && Object.keys(server.fields).length === 0 && <FormError error={server} />}
          <div className="flex flex-col gap-2">
            <Label htmlFor="current-password">Current password</Label>
            <Input
              id="current-password"
              type="password"
              autoComplete="current-password"
              value={current}
              onChange={(e) => setCurrent(e.target.value)}
              aria-invalid={!!server?.fieldError("current_password") || (submitted && !current)}
            />
            {(server?.fieldError("current_password") ?? (submitted && !current)) && (
              <p className="text-destructive text-sm">{server?.fieldError("current_password") ?? "Enter your current password."}</p>
            )}
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="new-password">New password</Label>
            <Input
              id="new-password"
              type="password"
              autoComplete="new-password"
              value={next}
              onChange={(e) => setNext(e.target.value)}
              aria-invalid={tooShort || !!server?.fieldError("new_password")}
            />
            {(tooShort || server?.fieldError("new_password")) && (
              <p className="text-destructive text-sm">
                {tooShort ? "Use at least 12 characters." : server?.fieldError("new_password")}
              </p>
            )}
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="confirm-password">Type it again</Label>
            <Input
              id="confirm-password"
              type="password"
              autoComplete="new-password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              aria-invalid={mismatch}
            />
            {mismatch && <p className="text-destructive text-sm">The two passwords don't match.</p>}
          </div>
          <Button type="submit" variant="cta" className="self-start" disabled={change.isPending}>
            {change.isPending && <Loader2 className="size-4 animate-spin" />} Change password
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

function PasswordPrompt({
  title,
  description,
  confirmLabel,
  onClose,
  onConfirm,
  pending,
  error,
}: {
  title: string;
  description: string;
  confirmLabel: string;
  onClose: () => void;
  onConfirm: (password: string) => void;
  pending: boolean;
  error: unknown;
}) {
  const [password, setPassword] = useState("");
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        <form
          id="password-prompt"
          className="flex flex-col gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            onConfirm(password);
          }}
        >
          <FormError error={error} />
          <Label htmlFor="prompt-password">Your password</Label>
          <Input
            id="prompt-password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </form>
        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="password-prompt" disabled={!password || pending}>
            {pending && <Loader2 className="size-4 animate-spin" />} {confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function SecurityCard({ me }: { me: Extract<Me, { authenticated: true }> }) {
  const qc = useQueryClient();
  const [dialog, setDialog] = useState<"setup" | "disable" | "codes" | null>(null);
  const [newCodes, setNewCodes] = useState<string[] | null>(null);
  const tf = me.two_factor;

  const disable = useMutation({
    mutationFn: (password: string) => api<Me>("/api/v1/auth/2fa/disable", { method: "POST", body: { password } }),
    onSuccess: (data) => {
      qc.setQueryData(meKey, data);
      setDialog(null);
      toast.success("Two-factor sign-in is off");
    },
  });
  const regen = useMutation({
    mutationFn: (password: string) =>
      api<{ recovery_codes: string[] }>("/api/v1/auth/2fa/recovery-codes", { method: "POST", body: { password } }),
    onSuccess: (data) => {
      setNewCodes(data.recovery_codes);
      setDialog(null);
      void qc.invalidateQueries({ queryKey: meKey });
    },
  });

  return (
    <Card id="security">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <ShieldCheck className="size-5" aria-hidden="true" /> Two-factor sign-in
        </CardTitle>
        <CardDescription>
          A code from your phone is needed each time you sign in, so a stolen password alone isn't enough.
          {tf.required && " Required for admins."}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="bg-muted/60 flex items-center gap-3 rounded-xl border p-4">
          {tf.enabled ? (
            <ShieldCheck className="text-success size-6" aria-hidden="true" />
          ) : (
            <ShieldOff className="text-muted-foreground size-6" aria-hidden="true" />
          )}
          <div className="flex-1">
            <p className="font-semibold">{tf.enabled ? "On" : "Off"}</p>
            {tf.enabled && (
              <p className="text-muted-foreground text-sm">{tf.recovery_codes_left} recovery codes left</p>
            )}
          </div>
        </div>
        {newCodes && (
          <div className="flex flex-col gap-2">
            <p className="font-semibold">Your new recovery codes</p>
            <p className="text-muted-foreground text-sm">The old ones no longer work. Save these somewhere safe.</p>
            <RecoveryCodes codes={newCodes} />
          </div>
        )}
        <div className="flex flex-wrap gap-2">
          {!tf.enabled && (
            <Button variant="cta" onClick={() => setDialog("setup")}>
              Set up two-factor
            </Button>
          )}
          {tf.enabled && (
            <Button variant="outline" onClick={() => setDialog("codes")}>
              New recovery codes
            </Button>
          )}
          {tf.enabled && !tf.required && (
            <Button variant="outline" onClick={() => setDialog("disable")}>
              Turn off
            </Button>
          )}
        </div>
      </CardContent>

      {dialog === "setup" && (
        <Dialog open onOpenChange={(open) => !open && setDialog(null)}>
          <DialogContent className="max-h-[92dvh] overflow-y-auto sm:max-w-xl">
            <DialogHeader>
              <DialogTitle>Set up two-factor sign-in</DialogTitle>
              <DialogDescription>About a minute. You'll need your phone.</DialogDescription>
            </DialogHeader>
            <TwoFactorSetupFlow
              onDone={() => {
                setDialog(null);
                toast.success("Two-factor sign-in is on");
              }}
            />
          </DialogContent>
        </Dialog>
      )}
      {dialog === "disable" && (
        <PasswordPrompt
          title="Turn off two-factor sign-in?"
          description="Your account will be protected by your password only."
          confirmLabel="Turn off"
          onClose={() => setDialog(null)}
          onConfirm={(pw) => disable.mutate(pw)}
          pending={disable.isPending}
          error={disable.error}
        />
      )}
      {dialog === "codes" && (
        <PasswordPrompt
          title="Make new recovery codes?"
          description="Your current recovery codes will stop working."
          confirmLabel="Make new codes"
          onClose={() => setDialog(null)}
          onConfirm={(pw) => regen.mutate(pw)}
          pending={regen.isPending}
          error={regen.error}
        />
      )}
    </Card>
  );
}

export function AccountPage() {
  const { data } = useMe();
  if (!data?.authenticated) return null;
  const u = data.user;
  return (
    <>
      <PageHeader title="My account" description="Your profile and how you sign in." />
      <div className="grid gap-6 xl:grid-cols-2">
        <Card className="xl:col-span-2">
          <CardContent className="flex flex-col gap-4 sm:flex-row sm:items-center">
            <div className="bg-primary text-primary-foreground grid size-14 place-items-center rounded-2xl">
              <UserRound className="size-7" aria-hidden="true" />
            </div>
            <div className="flex-1">
              <p className="text-xl font-bold">{u.full_name || u.email}</p>
              <p className="text-muted-foreground">{u.email}</p>
            </div>
            <Badge className="bg-primary text-primary-foreground w-fit text-sm">{u.role_label}</Badge>
          </CardContent>
        </Card>
        <SecurityCard me={data} />
        <PasswordCard />
      </div>
      <p className="text-muted-foreground mt-6 text-sm">To change your name, email or role, ask an admin.</p>
    </>
  );
}
