import { act, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { resolveTheme, ThemeProvider, useTheme } from "./theme";

function Probe() {
  const { theme, resolved, setTheme } = useTheme();
  return (
    <button type="button" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>
      {theme}/{resolved}
    </button>
  );
}

describe("theme", () => {
  it("resolves system to the device setting", () => {
    expect(resolveTheme("system", true)).toBe("dark");
    expect(resolveTheme("system", false)).toBe("light");
    expect(resolveTheme("light", true)).toBe("light");
  });

  it("applies the dark class and remembers the choice", () => {
    render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>,
    );
    expect(screen.getByRole("button")).toHaveTextContent("system/light");
    act(() => screen.getByRole("button").click());
    expect(document.documentElement).toHaveClass("dark");
    expect(localStorage.getItem("mmh-theme")).toBe("dark");
    act(() => screen.getByRole("button").click());
    expect(document.documentElement).not.toHaveClass("dark");
  });
});
