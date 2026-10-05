import { ApiError, readCookie } from "./api";

/** Multipart POST with upload progress (fetch can't report upload progress). */
export function uploadForm<T>(
  url: string,
  fields: Record<string, string | Blob>,
  onProgress?: (fraction: number) => void,
): Promise<T> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", url);
    xhr.withCredentials = true;
    xhr.setRequestHeader("X-CSRFToken", readCookie("mmh_csrftoken") ?? "");
    xhr.setRequestHeader("Accept", "application/json");
    if (onProgress) xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total);
    xhr.onload = () => {
      let body: { code?: string; detail?: string; fields?: Record<string, string[]> } = {};
      try {
        body = JSON.parse(xhr.responseText) as typeof body;
      } catch {
        // non-JSON error page
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(body as unknown as T);
      else
        reject(
          new ApiError(
            xhr.status,
            body.code ?? "upload_failed",
            body.fields?.file?.[0] ?? body.detail ?? "Upload failed. Try again.",
            body.fields ?? {},
          ),
        );
    };
    xhr.onerror = () => reject(new ApiError(0, "network", "Upload failed: check your connection."));
    const form = new FormData();
    for (const [key, value] of Object.entries(fields)) form.append(key, value);
    xhr.send(form);
  });
}
