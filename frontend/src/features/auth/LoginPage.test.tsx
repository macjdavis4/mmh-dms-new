import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockApi, renderWithProviders } from "@/test/utils";

import { LoginPage } from "./LoginPage";

afterEach(() => vi.unstubAllGlobals());

describe("LoginPage", () => {
  it("validates inline before calling the server", async () => {
    const spy = mockApi(() => ({ body: { authenticated: false } }));
    renderWithProviders(<LoginPage />, { path: "/login" });
    await userEvent.click(await screen.findByRole("button", { name: /sign in/i }));
    expect(screen.getByText("Enter a valid email address.")).toBeInTheDocument();
    expect(screen.getByText("Enter your password.")).toBeInTheDocument();
    expect(spy.mock.calls.filter(([u]) => u === "/api/v1/auth/login")).toHaveLength(0);
  });

  it("shows the server's message for a wrong password", async () => {
    document.cookie = "mmh_csrftoken=t";
    mockApi((url) =>
      url === "/api/v1/auth/login"
        ? { status: 400, body: { code: "invalid_credentials", detail: "Email or password is incorrect." } }
        : { body: { authenticated: false } },
    );
    renderWithProviders(<LoginPage />, { path: "/login" });
    await userEvent.type(await screen.findByLabelText("Email"), "pat@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "wrong-password");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Email or password is incorrect.");
  });

  it("asks for a code when two-factor is on", async () => {
    document.cookie = "mmh_csrftoken=t";
    mockApi((url) =>
      url === "/api/v1/auth/login" ? { body: { status: "otp_required" } } : { body: { authenticated: false } },
    );
    renderWithProviders(<LoginPage />, { path: "/login" });
    await userEvent.type(await screen.findByLabelText("Email"), "boss@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "Correct-Horse-1");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    await waitFor(() => expect(screen.getByRole("heading", { name: "Enter your code" })).toBeInTheDocument());
    expect(screen.getByRole("button", { name: /verify/i })).toBeDisabled();
  });
});
