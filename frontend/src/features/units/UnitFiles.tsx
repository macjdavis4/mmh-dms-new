import { useQueryClient } from "@tanstack/react-query";
import { Camera, ExternalLink, FileText, ImagePlus, Loader2, MoreHorizontal, Star, Trash2, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { api, ApiError } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { UnitFile } from "@/lib/types";
import { cn } from "@/lib/utils";

import { unitKeys, uploadUnitFile } from "./api";
import { UnitPhoto } from "./bits";

const PHOTO_TYPES = "image/jpeg,image/png,image/webp";
const DOC_TYPES = "image/jpeg,image/png,image/webp,application/pdf";

function useFileActions(unitId: string) {
  const qc = useQueryClient();
  const refresh = () => {
    void qc.invalidateQueries({ queryKey: unitKeys.detail(unitId) });
    void qc.invalidateQueries({ queryKey: unitKeys.all });
  };
  const [progress, setProgress] = useState<Record<string, number>>({});

  async function upload(files: FileList | null, kind: UnitFile["kind"]) {
    if (!files) return;
    for (const file of Array.from(files)) {
      const key = `${file.name}-${file.size}`;
      setProgress((p) => ({ ...p, [key]: 0 }));
      try {
        await uploadUnitFile(unitId, file, kind, (f) => setProgress((p) => ({ ...p, [key]: f })));
        toast.success(`${file.name} uploaded`);
      } catch (err) {
        toast.error(err instanceof ApiError ? err.message : "Upload failed");
      } finally {
        setProgress((p) => {
          const { [key]: _done, ...rest } = p;
          return rest;
        });
        refresh();
      }
    }
  }

  async function makeMain(file: UnitFile) {
    await api(`/api/v1/unit-files/${file.id}`, { method: "PATCH", body: { is_primary: true } });
    toast.success("Main photo changed");
    refresh();
  }

  async function remove(file: UnitFile) {
    await api(`/api/v1/unit-files/${file.id}`, { method: "DELETE" });
    refresh();
    toast.success(`${file.kind === "photo" ? "Photo" : "File"} removed`, {
      action: {
        label: "Undo",
        onClick: () => void api(`/api/v1/unit-files/${file.id}/restore`, { method: "POST" }).then(refresh),
      },
    });
  }

  return { upload, makeMain, remove, uploading: Object.values(progress) };
}

function UploadProgress({ values }: { values: number[] }) {
  if (values.length === 0) return null;
  const avg = values.reduce((a, b) => a + b, 0) / values.length;
  return (
    <div role="status" className="flex items-center gap-3 text-sm">
      <Loader2 className="size-4 animate-spin" aria-hidden="true" />
      <span>
        Uploading {values.length} {values.length === 1 ? "file" : "files"}… {Math.round(avg * 100)}%
      </span>
      <span className="bg-muted h-2 flex-1 overflow-hidden rounded-full">
        <span className="bg-primary block h-full transition-[width]" style={{ width: `${avg * 100}%` }} />
      </span>
    </div>
  );
}

export function UnitGallery({
  unitId,
  title,
  files,
  canEdit,
}: {
  unitId: string;
  title: string;
  files: UnitFile[];
  canEdit: boolean;
}) {
  const photos = files.filter((f) => f.kind === "photo");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [lightbox, setLightbox] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const actions = useFileActions(unitId);
  const selected = photos.find((p) => p.id === selectedId) ?? photos.find((p) => p.is_primary) ?? photos[0];

  return (
    <div className="flex flex-col gap-3">
      <div className="relative overflow-hidden rounded-xl border">
        {selected ? (
          <button type="button" onClick={() => setLightbox(true)} className="block w-full" aria-label="View larger">
            <img
              src={selected.url}
              alt={selected.caption || title}
              className="bg-muted aspect-[4/3] w-full object-cover"
              decoding="async"
            />
          </button>
        ) : (
          <UnitPhoto photoId={null} alt={title} className="aspect-[4/3] w-full" />
        )}
        {canEdit && photos.length === 0 && (
          <div className="absolute inset-x-0 bottom-0 flex justify-center p-4">
            <Button variant="cta" onClick={() => input.current?.click()}>
              <Camera className="size-5" /> Add photos
            </Button>
          </div>
        )}
      </div>

      {(photos.length > 0 || canEdit) && (
        <ul className="flex gap-2 overflow-x-auto pb-1" aria-label="Photos">
          {photos.map((p) => (
            <li key={p.id} className="relative shrink-0">
              <button
                type="button"
                onClick={() => setSelectedId(p.id)}
                aria-label={`Show photo${p.caption ? `: ${p.caption}` : ""}`}
                aria-current={selected?.id === p.id}
                className={cn(
                  "block overflow-hidden rounded-lg border-2",
                  selected?.id === p.id ? "border-cta" : "border-transparent",
                )}
              >
                <img src={p.thumbnail_url ?? p.url} alt="" className="bg-muted h-16 w-20 object-cover" loading="lazy" />
              </button>
              {p.is_primary && (
                <span className="bg-cta text-cta-foreground absolute top-1 left-1 grid size-5 place-items-center rounded-full" title="Main photo">
                  <Star className="size-3" aria-label="Main photo" />
                </span>
              )}
              {canEdit && (
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <button
                      type="button"
                      className="bg-card/90 absolute top-1 right-1 grid size-7 place-items-center rounded-md shadow"
                      aria-label="Photo actions"
                    >
                      <MoreHorizontal className="size-4" />
                    </button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    {!p.is_primary && (
                      <DropdownMenuItem className="min-h-10" onSelect={() => void actions.makeMain(p)}>
                        <Star className="size-4" /> Make main photo
                      </DropdownMenuItem>
                    )}
                    <DropdownMenuItem variant="destructive" className="min-h-10" onSelect={() => void actions.remove(p)}>
                      <Trash2 className="size-4" /> Remove photo
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              )}
            </li>
          ))}
          {canEdit && (
            <li className="shrink-0">
              <button
                type="button"
                onClick={() => input.current?.click()}
                className="text-muted-foreground hover:text-foreground hover:border-primary/50 grid h-16 w-20 place-items-center rounded-lg border-2 border-dashed"
                aria-label="Add photos"
              >
                <ImagePlus className="size-6" />
              </button>
            </li>
          )}
        </ul>
      )}
      <UploadProgress values={actions.uploading} />
      <input
        ref={input}
        type="file"
        accept={PHOTO_TYPES}
        multiple
        hidden
        data-testid="photo-input"
        onChange={(e) => {
          void actions.upload(e.target.files, "photo");
          e.target.value = "";
        }}
      />

      {selected && (
        <Dialog open={lightbox} onOpenChange={setLightbox}>
          <DialogContent className="max-w-[min(96vw,1400px)] p-2 sm:max-w-[min(96vw,1400px)]">
            <DialogTitle className="sr-only">{title}</DialogTitle>
            <DialogDescription className="sr-only">{selected.caption || "Photo"}</DialogDescription>
            <img src={selected.url} alt={selected.caption || title} className="max-h-[85dvh] w-full rounded-md object-contain" />
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}

export function UnitDocuments({ unitId, files, canEdit }: { unitId: string; files: UnitFile[]; canEdit: boolean }) {
  const docs = files.filter((f) => f.kind !== "photo");
  const input = useRef<HTMLInputElement>(null);
  const actions = useFileActions(unitId);
  return (
    <div className="flex flex-col gap-4">
      {docs.length === 0 ? (
        <p className="text-muted-foreground text-sm">
          No scanned card yet. Photograph or scan the original paper card so it stays with the unit.
        </p>
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2">
          {docs.map((d) => (
            <li key={d.id} className="flex items-center gap-3 rounded-xl border p-3">
              <a href={d.url} target="_blank" rel="noreferrer" className="shrink-0" aria-label={`Open ${d.caption || d.kind_label}`}>
                {d.thumbnail_url ? (
                  <img src={d.thumbnail_url} alt="" className="bg-muted h-20 w-28 rounded-md object-cover" loading="lazy" />
                ) : (
                  <span className="bg-muted grid h-20 w-28 place-items-center rounded-md">
                    <FileText className="text-muted-foreground size-8" aria-hidden="true" />
                  </span>
                )}
              </a>
              <div className="min-w-0 flex-1">
                <p className="truncate font-semibold">{d.caption || d.kind_label}</p>
                <p className="text-muted-foreground text-xs">
                  {d.kind_label} · {formatDate(d.created_at.slice(0, 10))}
                </p>
                <a href={d.url} target="_blank" rel="noreferrer" className="text-primary mt-1 inline-flex items-center gap-1 text-sm font-medium hover:underline">
                  Open <ExternalLink className="size-3.5" aria-hidden="true" />
                </a>
              </div>
              {canEdit && (
                <Button variant="ghost" size="icon" aria-label={`Remove ${d.caption || d.kind_label}`} onClick={() => void actions.remove(d)}>
                  <Trash2 className="size-4" />
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
      <UploadProgress values={actions.uploading} />
      {canEdit && (
        <div>
          <Button variant="outline" onClick={() => input.current?.click()}>
            <Upload className="size-4" /> Upload scanned card
          </Button>
          <input
            ref={input}
            type="file"
            accept={DOC_TYPES}
            hidden
            data-testid="card-input"
            onChange={(e) => {
              void actions.upload(e.target.files, "scanned_card");
              e.target.value = "";
            }}
          />
        </div>
      )}
    </div>
  );
}
