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

// --- Phase 2: customers and units ---------------------------------------------------

export interface Contact {
  id: string;
  customer: string;
  first_name: string;
  last_name: string;
  full_name: string;
  title: string;
  phone: string;
  mobile: string;
  email: string;
  is_primary: boolean;
  notes: string;
}

export type AddressKind = "billing" | "shipping" | "site" | "other";

export interface Address {
  id: string;
  customer: string;
  kind: AddressKind;
  label: string;
  line1: string;
  line2: string;
  city: string;
  state: string;
  postal_code: string;
  country: string;
  is_primary: boolean;
  notes: string;
  one_line: string;
}

export interface CustomerRow {
  id: string;
  name: string;
  kind: "business" | "individual";
  account_number: string;
  phone: string;
  email: string;
  primary_contact: string | null;
  city: string | null;
  unit_count: number;
  is_deleted: boolean;
}

export interface Customer {
  id: string;
  name: string;
  kind: "business" | "individual";
  account_number: string;
  phone: string;
  email: string;
  website: string;
  notes: string;
  contacts: Contact[];
  addresses: Address[];
  is_deleted: boolean;
  created_at: string;
  updated_at: string;
}

export type Condition = "new" | "used";
export type StockStatus = "" | "available" | "on_hold" | "in_prep" | "sold";
export type FuelType = "" | "lpg" | "gasoline" | "diesel" | "dual" | "electric" | "other";

export const STOCK_STATUS_LABELS: Record<Exclude<StockStatus, "">, string> = {
  available: "Available",
  on_hold: "On hold",
  in_prep: "In prep",
  sold: "Sold",
};

export const FUEL_LABELS: Record<Exclude<FuelType, "">, string> = {
  lpg: "LPG",
  gasoline: "Gasoline",
  diesel: "Diesel",
  dual: "Dual fuel",
  electric: "Electric",
  other: "Other",
};

export interface UnitRow {
  id: string;
  make: string;
  model: string;
  serial_number: string;
  stock_number: string;
  year: number | null;
  condition: Condition;
  fuel_type: FuelType;
  capacity_lbs: number | null;
  mast_lift_height_in: number | null;
  stock_status: StockStatus;
  needs_review: boolean;
  current_hours: string | null;
  owner_kind: "customer" | "dealer" | null;
  owner_customer_id: string | null;
  owner_name: string | null;
  primary_photo_id: string | null;
  asking_price?: string | null;
  is_deleted: boolean;
}

export type ComponentKind =
  | "engine"
  | "alternator"
  | "controller"
  | "ignition"
  | "fuel_system"
  | "hydraulic_pump"
  | "control_valve"
  | "transmission";

export const COMPONENT_KINDS: { kind: ComponentKind; label: string }[] = [
  { kind: "engine", label: "Engine" },
  { kind: "alternator", label: "Generator / alternator" },
  { kind: "controller", label: "Electrical controller" },
  { kind: "ignition", label: "Ignition system" },
  { kind: "fuel_system", label: "Fuel system" },
  { kind: "hydraulic_pump", label: "Hydraulic pump" },
  { kind: "control_valve", label: "Control valve" },
  { kind: "transmission", label: "Transmission" },
];

export interface UnitComponent {
  id?: string;
  kind: ComponentKind;
  kind_label?: string;
  make: string;
  model: string;
  serial_number: string;
  spools: "" | "2SP" | "3SP" | "4SP";
}

export interface UnitFork {
  id?: string;
  dimensions: string;
  quantity: number;
  thickness_in?: string | null;
  width_in?: string | null;
  length_in?: string | null;
}

export interface UnitAttachment {
  id?: string;
  manufacturer: string;
  type: string;
  model: string;
  serial_number: string;
  date_code: string;
  hose_reel: boolean;
  internal_hose: boolean;
  reel_number: string;
  side: "" | "LH" | "RH";
}

/** Every editable unit field (the paper unit card plus stock and pricing). */
export interface UnitFields {
  make: string;
  model: string;
  serial_number: string;
  year: number | null;
  stock_number: string;
  card_date: string | null;
  card_customer_name: string;
  mechanic: string;
  work_order_number: string;
  condition: Condition;
  fuel_type: FuelType;
  capacity_lbs: number | null;
  mast_make: string;
  mast_type: string;
  mast_size: string;
  mast_lift_height_in: number | null;
  mast_lowered_height_in: number | null;
  lift_cylinder_number: string;
  carriage: string;
  backrest_height: string;
  backrest_width: string;
  tilt_forward_deg: string | null;
  tilt_back_deg: string | null;
  tilt_reference: string;
  tire_type: string;
  tire_drive_size: string;
  tire_steer_size: string;
  tire_notes: string;
  battery_make: string;
  battery_model: string;
  battery_serial: string;
  battery_volts: number | null;
  battery_amp_hours: number | null;
  battery_size: string;
  battery_weight_lbs: number | null;
  charger_make: string;
  charger_model: string;
  charger_serial: string;
  special_equipment: string;
  field_modifications: string;
  notes: string;
  stock_status: StockStatus;
  cost?: string | null;
  asking_price?: string | null;
  sale_price?: string | null;
  needs_review: boolean;
  review_note: string;
}

export interface Unit extends UnitFields {
  id: string;
  components: UnitComponent[];
  forks: UnitFork[];
  attachments: UnitAttachment[];
  current_hours: string | null;
  current_hours_date: string | null;
  owner_kind: "customer" | "dealer" | null;
  owner_customer_id: string | null;
  owner_name: string | null;
  primary_photo_id: string | null;
  is_deleted: boolean;
  created_at: string;
  updated_at: string;
}

export interface HourReading {
  id: string;
  reading_date: string;
  hours: string;
  source: "card" | "service" | "sale" | "manual";
  source_label: string;
  note: string;
  created_at: string;
}

export interface OwnershipRecord {
  id: string;
  owner_kind: "customer" | "dealer";
  customer: string | null;
  customer_name: string | null;
  owner_label: string;
  start_date: string;
  end_date: string | null;
  note: string;
}

export interface UnitFile {
  id: string;
  unit: string;
  kind: "photo" | "scanned_card" | "document";
  kind_label: string;
  original_name: string;
  content_type: string;
  size_bytes: number;
  width: number | null;
  height: number | null;
  caption: string;
  is_primary: boolean;
  url: string;
  thumbnail_url: string | null;
  created_at: string;
}

export interface UnitFacets {
  makes: string[];
  models: Record<string, string[]>;
  can_see_pricing: boolean;
}

// --- Imports (Phase 3) --------------------------------------------------------------------------

export type ImportStatus = "draft" | "queued" | "importing" | "imported" | "failed" | "undoing" | "undone" | "discarded";

export interface ImportMessage {
  column: string;
  message: string;
}

export interface ImportFile {
  id: string;
  original_name: string;
  content_type: string;
  size_bytes: number;
  created_at: string;
}

export interface ImportBatchRow {
  id: string;
  source: "csv" | "api";
  source_label: string;
  status: ImportStatus;
  status_label: string;
  filename: string;
  reference: string;
  on_existing: "update" | "skip";
  skip_invalid: boolean;
  counts: Partial<Record<string, number>>;
  row_count: number;
  created_at: string;
  created_by_name: string;
  validated_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  undone_at: string | null;
  undone_by_name: string;
  api_key_name: string;
  error: string;
  can_undo: boolean;
}

export interface ImportBatch extends ImportBatchRow {
  file_messages: ImportMessage[];
  files: ImportFile[];
}

export interface ImportRow {
  id: string;
  row_number: number;
  status: "ok" | "warning" | "error";
  plan: "" | "create" | "update" | "unchanged" | "skip";
  plan_label: string;
  errors: ImportMessage[];
  warnings: ImportMessage[];
  changes: string[];
  serial: string;
  label: string;
  customer_name: string;
  unit: string | null;
  result: "" | "created" | "updated" | "unchanged" | "skipped" | "failed";
  result_label: string;
  undo_result: string;
}

export interface ApiKey {
  id: string;
  name: string;
  prefix: string;
  created_at: string;
  created_by_name: string;
  last_used_at: string | null;
  revoked_at: string | null;
  is_active: boolean;
  key?: string;
}
