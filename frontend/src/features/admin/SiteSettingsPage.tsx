import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Lock, Megaphone } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { ErrorState, PageHeader } from "@/components/states";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { SiteSettings } from "@/lib/types";

const KEY = ["admin", "site-settings"];
const MAX_BANNER = 300;

function useSaveSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<SiteSettings>) =>
      api<SiteSettings>("/api/v1/admin/site-settings", { method: "PATCH", body }),
    onSuccess: (data) => {
      qc.setQueryData(KEY, data);
      void qc.invalidateQueries({ queryKey: ["system", "status"] });
    },
  });
}

function BannerForm({ saved, save }: { saved: SiteSettings; save: ReturnType<typeof useSaveSettings> }) {
  const [message, setMessage] = useState(saved.banner_message);
  const [level, setLevel] = useState<SiteSettings["banner_level"]>(saved.banner_level);
  const dirty = message !== saved.banner_message || level !== saved.banner_level;
  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate(
          { banner_message: message.trim(), banner_level: level },
          { onSuccess: () => toast.success(message.trim() ? "Banner updated" : "Banner removed") },
        );
      }}
    >
      <div className="flex flex-col gap-2">
        <Label htmlFor="banner">Message</Label>
        <Textarea
          id="banner"
          rows={3}
          maxLength={MAX_BANNER}
          placeholder="e.g. The system will be down for updates Saturday 7–8 AM."
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          aria-describedby="banner-count"
        />
        <p id="banner-count" className="text-muted-foreground text-right text-xs">
          {message.length}/{MAX_BANNER}
        </p>
      </div>
      <div className="flex flex-col gap-2">
        <Label htmlFor="banner-level">Style</Label>
        <Select value={level} onValueChange={(v) => setLevel(v as SiteSettings["banner_level"])}>
          <SelectTrigger id="banner-level" className="h-11 w-full sm:w-56">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="info">Information (navy)</SelectItem>
            <SelectItem value="warning">Warning (amber)</SelectItem>
            <SelectItem value="critical">Critical (red)</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button type="submit" variant="cta" disabled={!dirty || save.isPending}>
          {save.isPending && <Loader2 className="size-4 animate-spin" />} Save banner
        </Button>
        {saved.banner_message && (
          <Button
            type="button"
            variant="outline"
            onClick={() => {
              setMessage("");
              save.mutate({ banner_message: "" }, { onSuccess: () => toast.success("Banner removed") });
            }}
          >
            Remove banner
          </Button>
        )}
      </div>
    </form>
  );
}

export function SiteSettingsPage() {
  const settings = useQuery({ queryKey: KEY, queryFn: () => api<SiteSettings>("/api/v1/admin/site-settings") });
  const save = useSaveSettings();
  const [confirmReadOnly, setConfirmReadOnly] = useState<boolean | null>(null);
  if (settings.isError) return <ErrorState message="Couldn't load settings." onRetry={() => void settings.refetch()} />;

  return (
    <>
      <PageHeader title="Site settings" description="Switches that affect everyone using the system." />
      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <Lock className="size-5" aria-hidden="true" /> Read-only mode
            </CardTitle>
            <CardDescription>
              Pause all changes, for example during database maintenance or a data migration. People can still sign
              in and look things up. Only admins can turn it back off.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {settings.isPending ? (
              <Skeleton className="h-12" />
            ) : (
              <div className="bg-muted/60 flex items-center justify-between gap-4 rounded-xl border p-4">
                <div>
                  <Label htmlFor="read-only" className="text-base font-semibold">
                    {settings.data.read_only_mode ? "Read-only mode is ON" : "Read-only mode is off"}
                  </Label>
                  <p className="text-muted-foreground text-sm">
                    {settings.data.read_only_mode ? "Nobody can make changes right now." : "Everyone can work normally."}
                  </p>
                </div>
                <Switch
                  id="read-only"
                  className="scale-125"
                  checked={settings.data.read_only_mode}
                  onCheckedChange={(checked) => setConfirmReadOnly(checked)}
                />
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <Megaphone className="size-5" aria-hidden="true" /> Maintenance banner
            </CardTitle>
            <CardDescription>A message shown at the top of every screen, including the sign-in page.</CardDescription>
          </CardHeader>
          <CardContent>
            {settings.isPending ? (
              <Skeleton className="h-32" />
            ) : (
              <BannerForm
                key={`${settings.data.banner_message}|${settings.data.banner_level}`}
                saved={settings.data}
                save={save}
              />
            )}
          </CardContent>
        </Card>
      </div>
      {settings.data && (
        <p className="text-muted-foreground mt-6 text-sm">Last changed {formatDateTime(settings.data.updated_at)}</p>
      )}

      <AlertDialog open={confirmReadOnly !== null} onOpenChange={(open) => !open && setConfirmReadOnly(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{confirmReadOnly ? "Turn on read-only mode?" : "Turn off read-only mode?"}</AlertDialogTitle>
            <AlertDialogDescription>
              {confirmReadOnly
                ? "Everyone will be blocked from saving changes until you turn it off again. Work in progress that hasn't been saved will be lost if people keep typing."
                : "Everyone will be able to make changes again."}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="h-11">Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="h-11"
              onClick={() => {
                const value = confirmReadOnly ?? false;
                save.mutate(
                  { read_only_mode: value },
                  { onSuccess: () => toast.success(value ? "Read-only mode is on" : "Read-only mode is off") },
                );
                setConfirmReadOnly(null);
              }}
            >
              {confirmReadOnly ? "Turn on" : "Turn off"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
