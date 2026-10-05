import { useQueryClient } from "@tanstack/react-query";
import { AlertCircle, ArrowLeft, FileImage, FileSpreadsheet, Loader2, Upload, X } from "lucide-react";
import { type DragEvent, type ReactNode, useId, useRef, useState } from "react";
import { Link, useNavigate } from "react-router";
import { toast } from "sonner";

import { SectionCard } from "@/components/form/Field";
import { Button } from "@/components/ui/button";
import { ApiError, api } from "@/lib/api";
import { cn } from "@/lib/utils";

import { SAMPLE_URL, TEMPLATE_URL, createBatch, importKeys, uploadScan } from "./api";
import { formatBytes } from "./bits";

const SCAN_TYPES = "image/jpeg,image/png,image/webp,application/pdf";

function DropZone({
  inputId,
  accept,
  multiple,
  onFiles,
  icon,
  title,
  hint,
}: {
  inputId: string;
  accept: string;
  multiple?: boolean;
  onFiles: (files: File[]) => void;
  icon: ReactNode;
  title: string;
  hint: string;
}) {
  const [over, setOver] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const drop = (e: DragEvent<HTMLLabelElement>) => {
    e.preventDefault();
    setOver(false);
    onFiles(Array.from(e.dataTransfer.files));
  };
  return (
    <label
      htmlFor={inputId}
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={drop}
      className={cn(
        "hover:border-primary/60 hover:bg-muted/50 flex min-h-36 cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed p-6 text-center transition-colors",
        over && "border-primary bg-primary/5",
      )}
    >
      <span className="bg-muted grid size-12 place-items-center rounded-xl">{icon}</span>
      <span className="font-semibold">{title}</span>
      <span className="text-muted-foreground text-sm">{hint}</span>
      <input
        ref={input}
        id={inputId}
        type="file"
        accept={accept}
        multiple={multiple}
        className="sr-only"
        onChange={(e) => {
          onFiles(Array.from(e.target.files ?? []));
          e.target.value = "";
        }}
      />
    </label>
  );
}

export function NewImportPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const csvId = useId();
  const scansId = useId();
  const [csv, setCsv] = useState<File | null>(null);
  const [scans, setScans] = useState<File[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [step, setStep] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);

  const pickCsv = (files: File[]) => {
    const file = files[0];
    if (!file) return;
    setError(null);
    if (!/\.(csv|txt)$/i.test(file.name)) {
      setError(
        /\.xlsx?$/i.test(file.name)
          ? "That's an Excel workbook. In Excel use File → Save As → CSV UTF-8 (Comma delimited), then choose the .csv file."
          : "Choose a .csv file.",
      );
      return;
    }
    setCsv(file);
  };

  const addScans = (files: File[]) => {
    const known = new Set(scans.map((f) => f.name.toLowerCase()));
    setScans([...scans, ...files.filter((f) => !known.has(f.name.toLowerCase()))]);
  };

  async function start() {
    if (!csv) return;
    setError(null);
    try {
      setStep("Uploading the spreadsheet…");
      setProgress(0);
      const batch = await createBatch(csv, setProgress);
      const failed: string[] = [];
      for (const [i, file] of scans.entries()) {
        setStep(`Uploading scans: ${i + 1} of ${scans.length}…`);
        setProgress(0);
        try {
          await uploadScan(batch.id, file, setProgress);
        } catch (err) {
          failed.push(`${file.name}: ${err instanceof ApiError ? err.message : "upload failed"}`);
        }
      }
      if (scans.length > 0) {
        setStep("Checking the rows…");
        await api(`/api/v1/imports/batches/${batch.id}/validate`, { method: "POST" });
      }
      void qc.invalidateQueries({ queryKey: importKeys.all });
      if (failed.length) toast.warning(`${failed.length} scan(s) couldn't be uploaded`, { description: failed.slice(0, 3).join("\n") });
      toast.success("File checked. Nothing has changed yet.");
      void navigate(`/imports/${batch.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed. Check your connection and try again.");
      setStep(null);
    }
  }

  const busy = step !== null;
  const scanBytes = scans.reduce((sum, f) => sum + f.size, 0);

  return (
    <div className="flex flex-col gap-6 pb-28">
      <div>
        <Link to="/imports" className="text-muted-foreground hover:text-foreground inline-flex min-h-11 items-center gap-1 text-sm font-medium">
          <ArrowLeft className="size-4" /> Imports
        </Link>
        <h1 className="text-2xl font-extrabold tracking-tight sm:text-3xl">New import</h1>
        <p className="text-muted-foreground mt-1">You'll see every row before anything is saved.</p>
      </div>

      <SectionCard
        id="csv"
        title="1. The spreadsheet"
        description={
          <>
            A CSV file in the import format.{" "}
            <a href={TEMPLATE_URL} download className="text-primary font-medium hover:underline">
              Download the template
            </a>{" "}
            or{" "}
            <a href={SAMPLE_URL} download className="text-primary font-medium hover:underline">
              a filled-in sample
            </a>
            .
          </>
        }
      >
        {csv ? (
          <div className="flex items-center gap-3 rounded-xl border p-4">
            <FileSpreadsheet className="text-primary size-8 shrink-0" aria-hidden="true" />
            <div className="min-w-0 flex-1">
              <p className="truncate font-semibold">{csv.name}</p>
              <p className="text-muted-foreground text-sm">{formatBytes(csv.size)}</p>
            </div>
            <Button variant="ghost" size="icon" aria-label={`Remove ${csv.name}`} onClick={() => setCsv(null)} disabled={busy}>
              <X className="size-4" />
            </Button>
          </div>
        ) : (
          <DropZone
            inputId={csvId}
            accept=".csv,text/csv"
            onFiles={pickCsv}
            icon={<FileSpreadsheet className="text-muted-foreground size-6" />}
            title="Choose the CSV file"
            hint="or drop it here. In Excel: Save As → CSV UTF-8."
          />
        )}
        {error && (
          <p role="alert" className="text-destructive mt-3 flex items-start gap-2 text-sm font-medium">
            <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
            {error}
          </p>
        )}
      </SectionCard>

      <SectionCard
        id="scans"
        title="2. Scanned cards (optional)"
        description="Photos or PDFs of the paper cards. Each is attached to the unit whose source_image_filename matches its file name."
      >
        <DropZone
          inputId={scansId}
          accept={SCAN_TYPES}
          multiple
          onFiles={addScans}
          icon={<FileImage className="text-muted-foreground size-6" />}
          title="Choose scans"
          hint="JPEG, PNG, WebP or PDF, up to 25 MB each. You can pick many at once."
        />
        {scans.length > 0 && (
          <div className="mt-4">
            <div className="mb-2 flex items-center justify-between gap-3">
              <p className="text-sm font-semibold">
                {scans.length} {scans.length === 1 ? "scan" : "scans"} · {formatBytes(scanBytes)}
              </p>
              <Button variant="ghost" size="sm" onClick={() => setScans([])} disabled={busy}>
                Remove all
              </Button>
            </div>
            <ul className="max-h-64 divide-y overflow-y-auto rounded-xl border text-sm">
              {scans.map((f) => (
                <li key={f.name} className="flex items-center gap-3 px-3 py-2">
                  <FileImage className="text-muted-foreground size-4 shrink-0" aria-hidden="true" />
                  <span className="min-w-0 flex-1 truncate">{f.name}</span>
                  <span className="text-muted-foreground text-xs">{formatBytes(f.size)}</span>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="size-9"
                    aria-label={`Remove ${f.name}`}
                    disabled={busy}
                    onClick={() => setScans(scans.filter((s) => s !== f))}
                  >
                    <X className="size-4" />
                  </Button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </SectionCard>

      <div className="bg-card/95 supports-[backdrop-filter]:bg-card/85 fixed inset-x-0 bottom-0 z-20 border-t backdrop-blur lg:left-64">
        <div className="mx-auto flex max-w-7xl items-center justify-end gap-3 px-4 py-3 sm:px-6 lg:px-8">
          {busy && (
            <p role="status" className="text-muted-foreground mr-auto flex min-w-0 items-center gap-2 text-sm">
              <Loader2 className="size-4 shrink-0 animate-spin" aria-hidden="true" />
              <span className="truncate">
                {step} {progress > 0 && progress < 1 ? `${Math.round(progress * 100)}%` : ""}
              </span>
            </p>
          )}
          <Button variant="outline" asChild>
            <Link to="/imports">Cancel</Link>
          </Button>
          <Button variant="cta" size="lg" disabled={!csv || busy} onClick={() => void start()}>
            <Upload className="size-5" /> Check file
          </Button>
        </div>
      </div>
    </div>
  );
}
