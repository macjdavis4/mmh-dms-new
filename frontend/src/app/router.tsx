import { createBrowserRouter } from "react-router";

import { AuthLayout } from "@/features/auth/AuthLayout";
import { LoginPage } from "@/features/auth/LoginPage";
import { DashboardPage } from "@/features/dashboard/DashboardPage";
import { ComingSoonPage, NotFoundPage } from "@/features/misc/ComingSoonPage";

import { RequireAuth, RequireRole } from "./guards";
import { RouteError } from "./RouteError";

export const routes = [
  {
    path: "/login",
    element: (
      <AuthLayout>
        <LoginPage />
      </AuthLayout>
    ),
  },
  {
    path: "/setup-2fa",
    lazy: async () => ({ Component: (await import("@/features/auth/TwoFactorSetupPage")).TwoFactorSetupPage }),
  },
  {
    path: "/",
    element: <RequireAuth />,
    errorElement: <RouteError />,
    children: [
      { index: true, element: <DashboardPage /> },
      {
        path: "account",
        lazy: async () => ({ Component: (await import("@/features/account/AccountPage")).AccountPage }),
      },
      {
        path: "customers",
        lazy: async () => ({ Component: (await import("@/features/customers/CustomersPage")).CustomersPage }),
      },
      {
        path: "customers/:id",
        lazy: async () => ({
          Component: (await import("@/features/customers/CustomerDetailPage")).CustomerDetailPage,
        }),
      },
      {
        path: "units",
        lazy: async () => ({ Component: (await import("@/features/units/UnitsPage")).UnitsPage }),
      },
      {
        path: "units/new",
        lazy: async () => ({ Component: (await import("@/features/units/UnitFormPage")).UnitFormPage }),
      },
      {
        path: "units/:id",
        lazy: async () => ({ Component: (await import("@/features/units/UnitDetailPage")).UnitDetailPage }),
      },
      {
        path: "units/:id/edit",
        lazy: async () => ({ Component: (await import("@/features/units/UnitFormPage")).UnitFormPage }),
      },
      ...["service", "parts", "imports"].map((path) => ({
        path,
        element: <ComingSoonPage />,
      })),
      {
        element: <RequireRole roles={["admin", "sales"]} />,
        children: [{ path: "sales", element: <ComingSoonPage /> }],
      },
      {
        path: "admin",
        element: <RequireRole roles={["admin"]} />,
        children: [
          {
            path: "users",
            lazy: async () => ({ Component: (await import("@/features/admin/UsersPage")).UsersPage }),
          },
          {
            path: "settings",
            lazy: async () => ({ Component: (await import("@/features/admin/SiteSettingsPage")).SiteSettingsPage }),
          },
          {
            path: "audit",
            lazy: async () => ({ Component: (await import("@/features/admin/AuditLogPage")).AuditLogPage }),
          },
        ],
      },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];

export const router = createBrowserRouter(routes);
