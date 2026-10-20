export type Page<T> = {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
};

export type AdminUser = {
  id: string;
  email: string;
  display_name: string;
  is_active: boolean;
  last_login_at: string | null;
  last_password_change_at?: string | null;
  created_at?: string;
};

export type Session = {
  admin: AdminUser;
  csrf_token: string;
  expires_at: string;
  /**
   * Development preview only. The API returns it when the panel runs on a
   * preview host and the browser blocks third-party cookies; it is always null
   * in staging and production.
   */
  dev_session_token?: string | null;
};

export type ProjectStatus = "active" | "inactive";

/** Feature keys are open: the backend registry can add capabilities without a
 * frontend release. Known keys are offered as autocomplete only. */
export type FeatureKey =
  | "announcements"
  | "financial"
  | "support"
  | "performance"
  | "progress"
  | (string & {});

export type Feature = {
  key: FeatureKey;
  label: string;
  description?: string;
  enabled: boolean;
  implemented: boolean;
  settings?: Record<string, unknown>;
};

export type FeatureCatalogItem = {
  key: string;
  label: string;
  description: string;
  implemented: boolean;
  default_enabled: boolean;
  action: string | null;
  settings_schema: Record<string, unknown>;
};

export type ChannelKey = "telegram" | "bale" | "eitaa" | "smsir" | (string & {});

export type ChannelState = {
  key: string;
  label: string;
  description: string;
  recipient_hint: string;
  supports_keyboard: boolean;
  beta: boolean;
  docs_url: string | null;
  configured: boolean;
  mode: string;
};

export type ProjectChannel = {
  channel: string;
  label: string;
  enabled: boolean;
  configured: boolean;
  mode: string;
  beta: boolean;
  recipient_hint: string;
  settings: Record<string, unknown>;
};

export type LicenseStatus = "pending" | "active" | "revoked" | "expired";

export type License = {
  id: string;
  project_id: string;
  project_name?: string | null;
  code_prefix: string;
  status: LicenseStatus;
  effective_status: LicenseStatus;
  expires_at: string | null;
  activated_at: string | null;
  revoked_at: string | null;
  created_at: string;
};

export type LicenseCreated = License & { code: string };

export type MemberStatus = "pending_approval" | "active" | "revoked";

export type MemberChannelIdentity = {
  channel: string;
  external_id: string;
  label: string | null;
};

export type Member = {
  id: string;
  telegram_id: number | null;
  display_name: string;
  username: string | null;
  role: string;
  status: MemberStatus;
  activated_at: string | null;
  created_at: string;
  channel_identities?: MemberChannelIdentity[];
};

export type Project = {
  id: string;
  name: string;
  slug: string;
  client_name: string;
  description: string | null;
  status: ProjectStatus;
  is_demo: boolean;
  telegram_connected_at: string | null;
  archived_at: string | null;
  created_at: string;
  updated_at: string;
  features: Feature[];
  channels: ProjectChannel[];
  license: License | null;
  members: Member[];
  open_payments_count: number;
  notifications_count: number;
};

export type ProjectCreated = Project & { license_code: string | null };

export type ProjectListItem = {
  id: string;
  name: string;
  slug: string;
  client_name: string;
  status: ProjectStatus;
  is_demo: boolean;
  archived_at: string | null;
  created_at: string;
  telegram_connected: boolean;
  telegram_connected_at: string | null;
  employer: Member | null;
  license_status: LicenseStatus | null;
  license_expires_at: string | null;
  enabled_features: string[];
  open_payments_count: number;
  notifications_count: number;
  open_tickets?: number;
};

export type TicketStatus = "open" | "pending_admin" | "pending_employer" | "closed";
export type TicketPriority = "low" | "normal" | "high";

export type TicketAttachment = {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
};

export type TicketMessage = {
  id: string;
  author_type: "admin" | "employer" | "system";
  author_label: string | null;
  body: string;
  channel: string;
  created_at: string;
  attachments: TicketAttachment[];
};

export type TicketListItem = {
  id: string;
  project_id: string;
  project_name: string | null;
  subject: string;
  status: TicketStatus;
  priority: TicketPriority;
  created_by_type: string;
  preview: string | null;
  message_count: number;
  admin_unread: number;
  member_unread: number;
  last_message_at: string;
  is_overdue: boolean;
  created_at: string;
};

export type Ticket = TicketListItem & {
  messages: TicketMessage[];
  member_display_name: string | null;
  closed_at: string | null;
};

export type NotificationStatus =
  | "draft"
  | "queued"
  | "sending"
  | "sent"
  | "failed"
  | "retry_wait"
  | "cancelled";

export type NotificationType = "announcement" | "financial" | "system";

export type Delivery = {
  id: string;
  channel: string;
  recipient: string;
  chat_id: number | null;
  status: "pending" | "sending" | "sent" | "failed" | "unknown";
  attempt_no: number;
  telegram_message_id: number | null;
  error: string | null;
  is_mock: boolean;
  started_at: string;
  finished_at: string | null;
};

export type Notification = {
  id: string;
  project_id: string;
  type: NotificationType;
  title: string;
  body: string;
  status: NotificationStatus;
  scheduled_at: string | null;
  queued_at: string | null;
  sent_at: string | null;
  cancelled_at: string | null;
  attempt_count: number;
  last_error: string | null;
  telegram_message_id: number | null;
  channels: string[];
  created_at: string;
  updated_at: string;
  deliveries: Delivery[];
};

export type NotificationListItem = {
  id: string;
  project_id: string;
  project_name: string | null;
  type: NotificationType;
  title: string;
  status: NotificationStatus;
  scheduled_at: string | null;
  sent_at: string | null;
  attempt_count: number;
  last_error: string | null;
  is_mock: boolean;
  created_at: string;
};

export type PaymentStatus = "unpaid" | "paid" | "cancelled";
export type Currency = "IRR" | "IRT" | "USD" | "EUR";

export type Payment = {
  id: string;
  project_id: string;
  project_name: string | null;
  title: string;
  amount_minor: number;
  currency: Currency;
  due_at: string;
  status: PaymentStatus;
  notes: string | null;
  paid_at: string | null;
  cancelled_at: string | null;
  created_at: string;
  updated_at: string;
  is_overdue: boolean;
  next_reminder_at: string | null;
};

export type AuditLog = {
  id: string;
  actor_type: "admin" | "telegram_user" | "system";
  actor_label: string | null;
  action: string;
  action_label: string | null;
  entity_type: string;
  entity_id: string | null;
  project_id: string | null;
  context: Record<string, unknown>;
  created_at: string;
};

export type Dashboard = {
  projects_total: number;
  projects_active: number;
  notifications_total: number;
  queued_notifications: number;
  failed_notifications: number;
  open_payments: number;
  open_payments_amount_by_currency: Record<string, number>;
  pending_members: number;
  license_attention: number;
  recent_activity: AuditLog[];
  generated_at: string;
};

export type WorkerStatus = {
  status: "online" | "offline" | "unknown";
  last_seen_at: string | null;
  hostname: string | null;
};

export type SystemStatus = {
  environment: string;
  server_time: string;
  database: { status: string; dialect: string; latency_ms: number | null };
  worker: WorkerStatus;
  telegram: {
    mode: "http" | "mock";
    bot_configured: boolean;
    webhook_secret_configured: boolean;
    last_update_at: string | null;
    webhook_path: string;
  };
  timezone: string;
  payment_reminder_days_before: number;
  session_ttl_hours: number;
  https_required: boolean;
  site_url: string;
  pending_jobs: number;
  failed_jobs: number;
  embedded_worker: boolean;
  oldest_pending_seconds: number | null;
  queue_status: "idle" | "draining" | "stalled" | (string & {});
};

// ---------------------------------------------------------------------------
// Service catalog and pre-sales orders (ثبت سفارش)
// ---------------------------------------------------------------------------
export type ServiceQuestionType = "text" | "long_text" | "number" | "choice" | "phone";

export type ServiceQuestion = {
  id: string;
  key: string;
  label: string;
  help_text: string;
  field_type: ServiceQuestionType;
  required: boolean;
  options: string[];
  min_value: number | null;
  max_value: number | null;
  order_index: number;
  is_active: boolean;
};

export type ServiceQuestionInput = {
  key?: string | null;
  label: string;
  help_text?: string;
  field_type: ServiceQuestionType;
  required: boolean;
  options: string[];
  min_value?: number | null;
  max_value?: number | null;
  order_index?: number;
  is_active?: boolean;
};

export type ServiceItem = {
  id: string;
  parent_id: string | null;
  level: number;
  key: string;
  title: string;
  description: string;
  order_index: number;
  is_active: boolean;
  show_portfolio: boolean;
  portfolio_text: string;
  portfolio_url: string;
  questions: ServiceQuestion[];
  children: ServiceItem[];
  is_group: boolean;
};

export type ServiceItemInput = {
  key?: string | null;
  title: string;
  description?: string;
  order_index?: number;
  is_active?: boolean;
  show_portfolio?: boolean;
  portfolio_text?: string;
  portfolio_url?: string;
  questions?: ServiceQuestionInput[];
};

export type ServiceCategory = {
  id: string;
  key: string;
  title: string;
  description: string;
  emoji: string;
  order_index: number;
  is_active: boolean;
  show_portfolio: boolean;
  portfolio_text: string;
  portfolio_url: string;
  items: ServiceItem[];
};

export type ServiceCategoryInput = {
  key?: string | null;
  title: string;
  description?: string;
  emoji?: string;
  order_index?: number;
  is_active?: boolean;
  show_portfolio?: boolean;
  portfolio_text?: string;
  portfolio_url?: string;
};

export type ServiceCatalog = {
  categories: ServiceCategory[];
  seeded: boolean;
  public_categories: number;
};

export type OrderStatus = "new" | "contacted" | "quoted" | "won" | "lost" | "cancelled";

export type OrderListItem = {
  id: string;
  category_title: string;
  item_title: string;
  service_path: string;
  contact_name: string;
  contact_phone: string;
  status: OrderStatus;
  source: string;
  telegram_username: string | null;
  telegram_id: number | null;
  created_at: string;
  updated_at: string;
};

export type OrderAnswer = { key: string; label: string; value: string };

export type Order = OrderListItem & {
  answers: OrderAnswer[];
  admin_note: string;
};

export type OrderCounters = Record<OrderStatus | "total", number>;
