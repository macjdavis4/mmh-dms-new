import { createBrowserRouter } from "react-router";

import { AuthLayout } from "@/features/auth/AuthLayout";
import { LoginPage } from "@/features/auth/LoginPage";
import { DashboardPage } from "@/features/dashboard/DashboardPage";
import { NotFoundPage } from "@/features/misc/ComingSoonPage";

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
        element: <RequireRole roles={["admin", "sales", "read_only"]} />,
        children: [
          {
            path: "units/changes",
            lazy: async () => ({ Component: (await import("@/features/units/ChangesPage")).ChangesPage }),
          },
        ],
      },
      {
        path: "units/:id",
        lazy: async () => ({ Component: (await import("@/features/units/UnitDetailPage")).UnitDetailPage }),
      },
      {
        path: "units/:id/edit",
        lazy: async () => ({ Component: (await import("@/features/units/UnitFormPage")).UnitFormPage }),
      },
      {
        element: <RequireRole roles={["admin", "sales", "service"]} />,
        children: [
          {
            path: "imports",
            lazy: async () => ({ Component: (await import("@/features/imports/ImportsPage")).ImportsPage }),
          },
          {
            path: "imports/new",
            lazy: async () => ({ Component: (await import("@/features/imports/NewImportPage")).NewImportPage }),
          },
          {
            path: "imports/:id",
            lazy: async () => ({ Component: (await import("@/features/imports/ImportBatchPage")).ImportBatchPage }),
          },
        ],
      },
      {
        path: "service",
        lazy: async () => ({ Component: (await import("@/features/service/WorkOrdersPage")).WorkOrdersPage }),
      },
      {
        path: "service/maintenance",
        lazy: async () => ({ Component: (await import("@/features/service/MaintenancePage")).MaintenancePage }),
      },
      {
        path: "service/new",
        lazy: async () => ({ Component: (await import("@/features/service/NewWorkOrderPage")).NewWorkOrderPage }),
      },
      {
        path: "service/:id",
        lazy: async () => ({ Component: (await import("@/features/service/WorkOrderPage")).WorkOrderPage }),
      },
      {
        path: "parts",
        lazy: async () => ({ Component: (await import("@/features/parts/PartsPage")).PartsPage }),
      },
      {
        path: "parts/bins",
        lazy: async () => ({ Component: (await import("@/features/parts/BinsPage")).BinsPage }),
      },
      {
        element: <RequireRole roles={["admin", "parts"]} />,
        children: [
          {
            path: "parts/new",
            lazy: async () => ({ Component: (await import("@/features/parts/PartFormPage")).PartFormPage }),
          },
          {
            path: "parts/:id/edit",
            lazy: async () => ({ Component: (await import("@/features/parts/PartFormPage")).PartFormPage }),
          },
        ],
      },
      {
        path: "parts/:id",
        lazy: async () => ({ Component: (await import("@/features/parts/PartPage")).PartPage }),
      },
      {
        element: <RequireRole roles={["admin", "sales"]} />,
        children: [
          {
            path: "sales",
            lazy: async () => ({ Component: (await import("@/features/sales/SalesPage")).SalesPage }),
          },
          {
            path: "sales/new",
            lazy: async () => ({ Component: (await import("@/features/sales/QuotePage")).NewQuotePage }),
          },
          {
            path: "sales/:id",
            lazy: async () => ({ Component: (await import("@/features/sales/QuotePage")).QuotePage }),
          },
        ],
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
            path: "api-keys",
            lazy: async () => ({ Component: (await import("@/features/admin/ApiKeysPage")).ApiKeysPage }),
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
