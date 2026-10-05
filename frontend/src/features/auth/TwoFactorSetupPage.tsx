import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, Copy, Download, Loader2, ShieldCheck, Smartphone } from "lucide-react";
import { useEffect, useState } from "react";
import { Navigate, useNavigate } from "react-router";

import { FullPageLoading } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import { meKey, useMe } from "@/lib/auth";
import type { Me } from "@/lib/types";

import { AuthLayout } from "./AuthLayout";
import { FormError } from "./FormError";

interface SetupData {
  secret: string;
  otpauth_url: string;
  qr_code: string;
}

export function useTwoFactorSetup() {
  return useMutation({
    mutationFn: () => api<SetupData>("/api/v1/auth/2fa/setup", { method: "POST" }),
  });
}

export function useTwoFactorConfirm() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (code: string) =>
      api<{ recovery_codes: string[] } & Me>("/api/v1/auth/2fa/confirm", { method: "POST", body: { code } }),
    onSuccess: (data) => {
      const { recovery_codes: _codes, ...me } = data;
      qc.setQueryData(meKey, me);
    },
  });
}

function groupSecret(secret: string): string {
  return secret.replace(/(.{4})/g, "$1 ").trim();
}

export function RecoveryCodes({ codes }: { codes: string[] }) {
  const [copied, setCopied] = useState(false);
  const text = `Maine Material Handling DMS recovery codes\nEach code works once.\n\n${codes.join("\n")}\n`;
  const href = `data:text/plain;charset=utf-8,${encodeURIComponent(text)}`;
  return (
    <div className="flex flex-col gap-4">
      <ul className="bg-muted grid grid-cols-2 gap-2 rounded-xl p-4 font-mono text-base" aria-label="Recovery codes">
        {codes.map((c) => (
          <li key={c} className="bg-card rounded-md px-3 py-2 text-center">
            {c}
          </li>
        ))}
      </ul>
      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          variant="outline"
          onClick={() => {
            void navigator.clipboard.writeText(codes.join("\n")).then(() => setCopied(true));
          }}
        >
          {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
          {copied ? "Copied" : "Copy"}
        </Button>
        <Button asChild variant="outline">
          <a href={href} download="mmh-recovery-codes.txt">
            <Download className="size-4" /> Download
          </a>
        </Button>
      </div>
    </div>
  );
}

/** Setup flow used both at forced first sign-in (admins) and from My account. */
export function TwoFactorSetupFlow({ onDone }: { onDone: () => void }) {
  const setup = useTwoFactorSetup();
  const confirm = useTwoFactorConfirm();
  const [code, setCode] = useState("");
  const { mutate: startSetup } = setup;

  useEffect(() => {
    startSetup();
  }, [startSetup]);

  if (confirm.data) {
    return (
      <div className="flex flex-col gap-5">
        <div className="text-success flex items-center gap-2 font-semibold">
          <ShieldCheck className="size-5" aria-hidden="true" /> Two-factor sign-in is on.
        </div>
        <div>
          <h3 className="text-lg font-bold">Save your recovery codes</h3>
          <p className="text-muted-foreground mt-1 text-sm">
            If you lose your phone, each of these codes lets you sign in once. Store them somewhere safe, like a
            password manager or a printed copy in the office safe. You won't see them again.
          </p>
        </div>
        <RecoveryCodes codes={confirm.data.recovery_codes} />
        <Button variant="cta" size="lg" onClick={onDone}>
          I've saved my codes. Continue
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <ol className="flex flex-col gap-6">
        <li className="flex flex-col gap-3">
          <p className="font-semibold">
            <span className="bg-primary text-primary-foreground mr-2 inline-grid size-6 place-items-center rounded-full text-xs">
              1
            </span>
            Scan this with an authenticator app
          </p>
          <p className="text-muted-foreground text-sm">
            Google Authenticator, Microsoft Authenticator, 1Password or any app that supports “TOTP”.
          </p>
          <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-start">
            <div className="grid size-48 shrink-0 place-items-center rounded-xl border bg-white p-2">
              {setup.data ? (
                <img src={setup.data.qr_code} alt="QR code for your authenticator app" className="size-full" />
              ) : setup.isError ? (
                <span className="text-destructive text-sm">Couldn't load</span>
              ) : (
                <Loader2 className="size-6 animate-spin text-slate-500" aria-label="Loading QR code" />
              )}
            </div>
            <div className="text-sm">
              <p className="text-muted-foreground">Can't scan? Type this key into the app instead:</p>
              <p className="bg-muted mt-2 rounded-md px-3 py-2 font-mono text-base break-all" data-testid="totp-secret">
                {setup.data ? groupSecret(setup.data.secret) : "…"}
              </p>
            </div>
          </div>
        </li>
        <li className="flex flex-col gap-3">
          <p className="font-semibold">
            <span className="bg-primary text-primary-foreground mr-2 inline-grid size-6 place-items-center rounded-full text-xs">
              2
            </span>
            Enter the 6-digit code it shows
          </p>
          <form
            className="flex flex-col gap-3 sm:flex-row"
            noValidate
            onSubmit={(e) => {
              e.preventDefault();
              confirm.mutate(code.replace(/\s/g, ""));
            }}
          >
            <Label htmlFor="setup-code" className="sr-only">
              6-digit code
            </Label>
            <Input
              id="setup-code"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={7}
              value={code}
              onChange={(e) => setCode(e.target.value)}
              className="h-12 font-mono text-xl tracking-[0.3em] sm:w-48"
              aria-invalid={confirm.isError}
            />
            <Button
              type="submit"
              variant="cta"
              className="h-12"
              disabled={confirm.isPending || code.replace(/\s/g, "").length !== 6 || !setup.data}
            >
              {confirm.isPending ? <Loader2 className="size-5 animate-spin" /> : <ShieldCheck className="size-5" />}
              Turn on
            </Button>
          </form>
          <FormError error={confirm.error ?? setup.error} />
        </li>
      </ol>
    </div>
  );
}

export function TwoFactorSetupPage() {
  const me = useMe();
  const navigate = useNavigate();
  if (me.isPending) return <FullPageLoading />;
  if (!me.data?.authenticated) return <Navigate to="/login" replace />;
  return (
    <AuthLayout>
      <Card className="shadow-lg">
        <CardHeader>
          <div className="bg-primary/10 text-primary mb-2 grid size-12 place-items-center rounded-xl">
            <Smartphone className="size-6" aria-hidden="true" />
          </div>
          <CardTitle className="text-2xl font-extrabold">Set up two-factor sign-in</CardTitle>
          <CardDescription className="text-[15px]">
            {me.data.two_factor.required
              ? "Admins must confirm each sign-in with a code from their phone. This takes about a minute."
              : "Add a code from your phone to each sign-in."}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <TwoFactorSetupFlow onDone={() => void navigate("/", { replace: true })} />
        </CardContent>
      </Card>
    </AuthLayout>
  );
}
