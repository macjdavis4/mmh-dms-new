import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockApi, renderWithProviders } from "@/test/utils";

import { EnvironmentTag, SystemBanner } from "./SystemBanner";

afterEach(() => vi.unstubAllGlobals());

describe("SystemBanner", () => {
  it("shows the maintenance message and read-only notice", async () => {
    mockApi(() => ({
      body: {
        read_only_mode: true,
        banner_message: "Down for updates Saturday 7 AM",
        banner_level: "warning",
        environment: "staging",
        version: "1",
      },
    }));
    renderWithProviders(
      <>
        <SystemBanner />
        <EnvironmentTag />
      </>,
    );
    expect(await screen.findByText("Down for updates Saturday 7 AM")).toBeInTheDocument();
    expect(screen.getByText(/Read-only mode/)).toBeInTheDocument();
    expect(screen.getByText("staging")).toBeInTheDocument();
  });

  it("renders nothing when there is nothing to say", async () => {
    const spy = mockApi(() => ({
      body: { read_only_mode: false, banner_message: "", banner_level: "info", environment: "production", version: "1" },
    }));
    const { container } = renderWithProviders(<SystemBanner />);
    await vi.waitFor(() => expect(spy).toHaveBeenCalled());
    expect(container.querySelector('[role="status"]')).toBeNull();
  });
});
