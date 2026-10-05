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

export type OwnershipReason =
  | ""
  | "sold"
  | "private_sale"
  | "trade_in"
  | "repossession"
  | "buy_back"
  | "lease_return"
  | "bought_used"
  | "other";

export interface OwnershipRecord {
  id: string;
  owner_kind: "customer" | "dealer";
  customer: string | null;
  customer_name: string | null;
  owner_label: string;
  start_date: string;
  end_date: string | null;
  note: string;
  /** Blank: the first owner on record (or a change from before reasons were kept). */
  reason: OwnershipReason;
  reason_label: string;
  /** Admin and sales only: sale price, or what we paid when it came back. */
  price?: string | null;
  /** Admin and sales only: on a sale, the unit's cost at the time. */
  cost?: string | null;
  reference: string;
  hours: string | null;
  can_undo: boolean;
}

/** One row of "Bought and sold". */
export interface UnitChange {
  id: string;
  unit: string;
  unit_label: string;
  unit_make: string;
  unit_model: string;
  unit_serial: string;
  unit_stock_number: string;
  start_date: string;
  end_date: string | null;
  reason: OwnershipReason;
  reason_label: string;
  owner_kind: "customer" | "dealer";
  customer: string | null;
  owner_label: string;
  from_kind: "customer" | "dealer";
  from_customer: string | null;
  from_label: string;
  price?: string | null;
  cost?: string | null;
  reference: string;
  note: string;
  hours: string | null;
}

export interface UnitChangeTotals {
  sold: { count: number; total?: string | null; margin?: string | null; with_margin?: number };
  came_back: { count: number; total?: string | null };
  between_customers: { count: number };
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

// --- Service (Phase 4) --------------------------------------------------------------------------

export type WorkOrderStatus = "open" | "in_progress" | "on_hold" | "completed" | "cancelled";
export type WorkOrderKind = "repair" | "maintenance" | "inspection" | "prep" | "warranty";

export const WORK_ORDER_KINDS: Record<WorkOrderKind, string> = {
  repair: "Repair",
  maintenance: "Planned maintenance",
  inspection: "Inspection",
  prep: "Prep for sale",
  warranty: "Warranty",
};

export interface UnitSummary {
  id: string;
  make: string;
  model: string;
  serial_number: string;
  stock_number: string;
  year: number | null;
}

export interface WorkOrderRow {
  id: string;
  number: string;
  unit: string;
  unit_summary: UnitSummary;
  customer: string | null;
  customer_name: string;
  kind: WorkOrderKind;
  kind_label: string;
  status: WorkOrderStatus;
  status_label: string;
  location: "shop" | "field";
  assigned_to: string | null;
  assigned_to_name: string;
  complaint: string;
  hold_reason: string;
  opened_on: string;
  due_on: string | null;
  completed_at: string | null;
  labor_hours: string;
}

export interface LaborLine {
  id: string;
  work_order: string;
  mechanic: string;
  mechanic_name: string;
  work_date: string;
  hours: string;
  description: string;
  created_at: string;
}

export interface WorkOrder extends WorkOrderRow {
  location_label: string;
  cause: string;
  correction: string;
  customer_po: string;
  contact: string;
  notes: string;
  hour_meter: { hours: string; reading_date: string } | null;
  labor: LaborLine[];
  maintenance_plan: string | null;
  maintenance_plan_name: string;
  is_deleted: boolean;
  created_at: string;
  created_by_name: string;
  updated_at: string;
  warning?: string | null;
}

export interface Mechanic {
  id: string;
  name: string;
  role: string;
}

// --- Planned maintenance (Phase 5) -------------------------------------------------------------

export type PlanState = "overdue" | "due_soon" | "ok" | "paused";

export interface PlanStatus {
  state: PlanState;
  next_due_on: string | null;
  next_due_hours: string | null;
  current_hours: string | null;
  days_left: number | null;
  hours_left: string | null;
  open_work_order: { id: string; number: string; status: WorkOrderStatus } | null;
}

export interface MaintenancePlan {
  id: string;
  unit: string;
  unit_summary: UnitSummary;
  owner_name: string;
  name: string;
  tasks: string;
  interval_hours: number | null;
  interval_days: number | null;
  last_done_on: string;
  last_done_hours: string | null;
  active: boolean;
  status: PlanStatus | null;
  created_at: string;
}

// --- Sales (Phase 8) -------------------------------------------------------------------------

export type QuoteStatus = "draft" | "sent" | "accepted" | "declined" | "cancelled" | "sold";
export type QuoteLineKind = "unit" | "attachment" | "delivery" | "service" | "other" | "discount";

export const QUOTE_LINE_KINDS: Record<QuoteLineKind, string> = {
  unit: "Unit",
  attachment: "Attachment or option",
  delivery: "Delivery",
  service: "Service or warranty",
  other: "Other",
  discount: "Discount",
};

export interface SalesUnitSummary {
  id: string;
  make: string;
  model: string;
  serial_number: string;
  stock_number: string;
  year: number | null;
  condition: Condition;
  stock_status: StockStatus;
}

export interface QuoteLine {
  id?: string;
  kind: QuoteLineKind;
  kind_label?: string;
  unit: string | null;
  unit_summary?: SalesUnitSummary | null;
  description: string;
  quantity: string;
  unit_price: string;
  taxable: boolean;
  amount?: string;
}

export interface TradeIn {
  id?: string;
  unit: string | null;
  unit_summary?: SalesUnitSummary | null;
  make: string;
  model: string;
  serial_number: string;
  year: number | null;
  hours: string | null;
  description: string;
  allowance: string;
  payoff: string | null;
  payoff_to: string;
}

export interface QuoteTotals {
  subtotal: string;
  trade_allowance: string;
  trade_payoff: string;
  taxable_amount: string;
  tax_rate: string;
  tax: string;
  total: string;
}

export interface SaleSummary {
  id: string;
  number: string;
  status: "completed" | "voided";
  sale_date: string;
  invoice_number: string;
  total: string;
  void_reason: string;
}

export interface Quote {
  id: string;
  number: string;
  customer: string;
  customer_name: string;
  salesperson: string | null;
  salesperson_name: string;
  status: QuoteStatus;
  status_label: string;
  quote_date: string;
  valid_until: string | null;
  attention: string;
  customer_po: string;
  tax_rate: string;
  tax_exempt: boolean;
  tax_exempt_number: string;
  terms: string;
  notes: string;
  sent_at: string | null;
  decided_at: string | null;
  lines: QuoteLine[];
  trade_ins: TradeIn[];
  totals: QuoteTotals;
  is_expired: boolean;
  is_open: boolean;
  sale: SaleSummary | null;
  past_sales: SaleSummary[];
  created_at: string;
  updated_at: string;
}

export interface QuoteRow {
  id: string;
  number: string;
  customer: string;
  customer_name: string;
  salesperson_name: string;
  status: QuoteStatus;
  status_label: string;
  quote_date: string;
  valid_until: string | null;
  is_expired: boolean;
  total: string;
  units: string[];
  trade_in_count: number;
  sale_number: string | null;
}

// --- Parts (Phase 9) --------------------------------------------------------------------------

export interface PartBin {
  id: string;
  code: string;
  description: string;
  part_count: number;
}

export interface PartSummary {
  id: string;
  manufacturer: string;
  part_number: string;
  description: string;
  is_deleted: boolean;
}

export interface CrossReference {
  id?: string;
  manufacturer: string;
  part_number: string;
  note: string;
}

export interface PartRow {
  id: string;
  manufacturer: string;
  part_number: string;
  description: string;
  category: string;
  category_label: string;
  unit_of_measure: string;
  /** Admin, sales and parts only. */
  cost?: string | null;
  list_price: string | null;
  bin: string | null;
  bin_code: string | null;
  reorder_point: string | null;
  reorder_quantity: string | null;
  vendor: string;
  superseded_by: string | null;
  superseded_by_summary: PartSummary | null;
  is_deleted: boolean;
}

export interface Part extends PartRow {
  unit_label: string;
  vendor_part_number: string;
  fits: string;
  notes: string;
  superseded_on: string | null;
  current_part: PartSummary | null;
  supersedes: PartSummary[];
  cross_references: CrossReference[];
  created_at: string;
  updated_at: string;
}

export interface PartFacets {
  categories: { value: string; label: string }[];
  units: { value: string; label: string }[];
  can_see_cost: boolean;
}
