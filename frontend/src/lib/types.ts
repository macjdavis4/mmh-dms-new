export type Role = "admin" | "sales" | "service" | "parts" | "read_only";

export const ROLE_LABELS: Record<Role, string> = {
  admin: "Admin",
  sales: "Sales",
  service: "Service",
  parts: "Parts",
  read_only: "Read only",
};

export const ROLE_DESCRIPTIONS: Record<Role, string> = {
  admin: "Everything, including users, settings and pricing",
  sales: "Customers, units, quotes and pricing",
  service: "Work orders and unit records",
  parts: "Parts inventory and receiving",
  read_only: "Can look, cannot change anything",
};

export interface CurrentUser {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  full_name: string;
  role: Role;
  role_label: string;
  can_see_pricing: boolean;
}

export interface TwoFactorState {
  enabled: boolean;
  verified: boolean;
  required: boolean;
  setup_needed: boolean;
  recovery_codes_left: number;
}

export type Me =
  | { authenticated: false }
  | { authenticated: true; user: CurrentUser; two_factor: TwoFactorState };

export interface SystemStatus {
  read_only_mode: boolean;
  banner_message: string;
  banner_level: "info" | "warning" | "critical";
  environment: string;
  version: string;
}

export interface AdminUser {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  full_name: string;
  phone: string;
  role: Role;
  role_label: string;
  is_active: boolean;
  is_deleted: boolean;
  two_factor_enabled: boolean;
  last_login: string | null;
  created_at: string;
}

export interface SiteSettings {
  read_only_mode: boolean;
  banner_message: string;
  banner_level: "info" | "warning" | "critical";
  updated_at: string;
}

export interface AuditEntry {
  id: number;
  at: string;
  actor: string | null;
  actor_email: string | null;
  actor_role: string;
  source: string;
  action: string;
  action_label: string;
  object_type: string | null;
  object_id: string;
  object_repr: string;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  changed_fields: string[];
  request_id: string;
  ip: string | null;
}

export interface AdminHealth {
  database: string;
  migrations: string;
  jobs: Record<string, number>;
  last_backup: { status: string; started_at: string; finished_at: string | null } | null;
  version: string;
  environment: string;
}

export interface SearchResponse {
  query: string;
  groups: Record<string, { kind: string; id: string; title: string; subtitle: string; url: string }[]>;
  searchable: string[];
}
