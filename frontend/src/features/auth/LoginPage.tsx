import { ArrowLeft, Loader2, LogIn, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router";

import { FullPageLoading } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api";
import { useLogin, useMe, useVerifyCode } from "@/lib/auth";

import { FormError } from "./FormError";

function safeNext(raw: string | null): string {
  // Only allow in-app paths, never another site.
  return raw?.startsWith("/") && !raw.startsWith("//") ? raw : "/";
}

export function LoginPage() {
  const me = useMe();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const next = safeNext(params.get("next"));
  const [step, setStep] = useState<"password" | "code">("password");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [touched, setTouched] = useState(false);
  const login = useLogin();
  const verify = useVerifyCode();

  if (me.isPending) return <FullPageLoading />;
  if (me.data?.authenticated) {
    return <Navigate to={me.data.two_factor.setup_needed ? "/setup-2fa" : next} replace />;
  }

  const emailInvalid = touched && !/^\S+@\S+\.\S+$/.test(email);
  const passwordMissing = touched && password.length === 0;

  function submitPassword(e: React.SubmitEvent<HTMLFormElement>) {
    e.preventDefault();
    setTouched(true);
    if (!/^\S+@\S+\.\S+$/.test(email) || !password) return;
    login.mutate(
      { email, password },
      {
        onSuccess: (data) => {
          if (data.status === "otp_required") {
            setStep("code");
          } else if (data.authenticated && data.two_factor.setup_needed) {
            void navigate("/setup-2fa", { replace: true });
          } else {
            void navigate(next, { replace: true });
          }
        },
      },
    );
  }

  function submitCode(e: React.SubmitEvent<HTMLFormElement>) {
    e.preventDefault();
    verify.mutate(code, {
      onSuccess: () => void navigate(next, { replace: true }),
      onError: (err) => {
        if (err instanceof ApiError && err.code === "otp_expired") {
          setStep("password");
          setCode("");
        }
      },
    });
  }

  if (step === "code") {
    return (
      <Card className="shadow-lg">
        <CardHeader>
          <div className="bg-primary/10 text-primary mb-2 grid size-12 place-items-center rounded-xl">
            <ShieldCheck className="size-6" aria-hidden="true" />
          </div>
          <CardTitle className="text-2xl font-extrabold">Enter your code</CardTitle>
          <CardDescription className="text-[15px]">
            Open your authenticator app and type the 6-digit code for Maine Material Handling. Lost your
            phone? Use one of your recovery codes instead.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={submitCode} className="flex flex-col gap-5" noValidate>
            <FormError error={verify.error} />
            <div className="flex flex-col gap-2">
              <Label htmlFor="code">Code</Label>
              <Input
                id="code"
                inputMode="numeric"
                autoComplete="one-time-code"
                // eslint-disable-next-line jsx-a11y/no-autofocus -- single-purpose code entry step
                autoFocus
                maxLength={20}
                value={code}
                onChange={(e) => setCode(e.target.value)}
                className="h-14 text-center font-mono text-2xl tracking-[0.4em]"
                aria-invalid={verify.isError}
              />
            </div>
            <Button type="submit" variant="cta" className="h-12 text-base" disabled={verify.isPending || code.length < 6}>
              {verify.isPending ? <Loader2 className="size-5 animate-spin" /> : <ShieldCheck className="size-5" />}
              Verify and sign in
            </Button>
            <Button
              type="button"
              variant="ghost"
              className="h-11"
              onClick={() => {
                setStep("password");
                setCode("");
                verify.reset();
              }}
            >
              <ArrowLeft className="size-4" /> Use a different account
            </Button>
          </form>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="shadow-lg">
      <CardHeader>
        <CardTitle className="text-2xl font-extrabold">Sign in</CardTitle>
        <CardDescription className="text-[15px]">Staff only. Use your work email.</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={submitPassword} className="flex flex-col gap-5" noValidate>
          <FormError error={login.error} />
          <div className="flex flex-col gap-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              autoComplete="username"
              inputMode="email"
              // eslint-disable-next-line jsx-a11y/no-autofocus -- sign-in page: the email field is the only task
              autoFocus
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="h-12 text-base"
              aria-invalid={emailInvalid}
              aria-describedby={emailInvalid ? "email-error" : undefined}
            />
            {emailInvalid && (
              <p id="email-error" className="text-destructive text-sm">
                Enter a valid email address.
              </p>
            )}
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="h-12 text-base"
              aria-invalid={passwordMissing}
              aria-describedby={passwordMissing ? "password-error" : undefined}
            />
            {passwordMissing && (
              <p id="password-error" className="text-destructive text-sm">
                Enter your password.
              </p>
            )}
          </div>
          <Button type="submit" variant="cta" className="h-12 text-base" disabled={login.isPending}>
            {login.isPending ? <Loader2 className="size-5 animate-spin" /> : <LogIn className="size-5" />}
            Sign in
          </Button>
          <p className="text-muted-foreground text-center text-sm">
            Forgot your password? Ask an admin to set a new one.
          </p>
        </form>
      </CardContent>
    </Card>
  );
}
