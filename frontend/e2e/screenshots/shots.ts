import path from "node:path";

import type { Browser, Page } from "@playwright/test";

export const VIEWPORTS = {
  desktop: { width: 1440, height: 900 },
  tablet: { width: 1024, height: 768 },
  phone: { width: 390, height: 844 },
} as const;
export const THEMES = ["light", "dark"] as const;

export type Viewport = keyof typeof VIEWPORTS;
export type Theme = (typeof THEMES)[number];

export function outDir(phase: number): string {
  return process.env.SCREENSHOT_DIR ?? path.resolve(import.meta.dirname, `../../../docs/screenshots/phase-${phase}`);
}

export async function newPage(browser: Browser, viewport: Viewport, theme: Theme, storageState?: string): Promise<Page> {
  const context = await browser.newContext({
    viewport: VIEWPORTS[viewport],
    colorScheme: theme,
    reducedMotion: "reduce",
    deviceScaleFactor: 1,
    ...(storageState ? { storageState } : {}),
  });
  await context.addInitScript((t) => window.localStorage.setItem("mmh-theme", t), theme);
  return context.newPage();
}

/** Save `<name>-<viewport>-<theme>.png` once the network and fonts settle. */
export function shooter(out: string, viewport: Viewport, theme: Theme) {
  return async (page: Page, name: string, fullPage = true) => {
    await page.waitForLoadState("networkidle");
    await page.evaluate(() => document.fonts.ready);
    // Load lazy images too (a full-page shot shows them all), but never wait long.
    await page.evaluate(() =>
      Promise.race([
        Promise.all(
          Array.from(document.images).map((img) => {
            img.loading = "eager";
            return img.complete ? Promise.resolve() : new Promise((r) => img.addEventListener("load", r, { once: true }));
          }),
        ),
        new Promise((r) => setTimeout(r, 4000)),
      ]),
    );
    await page.screenshot({ path: path.join(out, `${name}-${viewport}-${theme}.png`), fullPage, animations: "disabled" });
  };
}
