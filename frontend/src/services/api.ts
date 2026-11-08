const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/api/v1';

export interface HealthStatus {
  status: string;
  app: string;
  version: string;
  database: string;
}

export interface DashboardOverview {
  total_employees: number;
  total_managers: number;
  total_goals: number;
  completed_goals: number;
  average_goal_progress: number | null;
  active_review_cycles: number;
  pending_reviews: number;
}

export interface GoalProgressBand {
  label: string;
  count: number;
}

export interface DepartmentPerformance {
  department: string;
  employee_count: number;
  goal_count: number;
  completed_goals: number;
  average_goal_progress: number | null;
}

export interface RecentCheckIn {
  id: string;
  employee_name: string;
  manager_name: string | null;
  checkin_date: string;
  status: string;
}

export interface DataQualityCheck {
  label: string;
  affected_records: number;
  passed: boolean;
}

export interface DataQualitySummary {
  status: 'healthy' | 'attention_required';
  checks_passed: number;
  checks_total: number;
  checks: DataQualityCheck[];
}

export interface DashboardAnalytics {
  overview: DashboardOverview;
  goal_progress_distribution: GoalProgressBand[];
  department_performance: DepartmentPerformance[];
  recent_check_ins: RecentCheckIn[];
  data_quality: DataQualitySummary;
}

export interface PageResult<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface DevelopmentPlanRecord {
  id: string;
  employee_id: string;
  employee_name: string;
  owner_manager_id: string;
  owner_manager_name: string;
  review_cycle_id: string | null;
  review_cycle_name: string | null;
  title: string;
  description: string;
  effective_from: string;
  effective_to: string | null;
  status: 'draft' | 'active' | 'completed' | 'cancelled';
  editable: boolean;
  approval_actionable: boolean;
  goals: Array<{ id: string; title: string }>;
  competencies: Array<{ id: string; name: string; category: string }>;
  approvals: Array<{
    approver_manager_id: string;
    approver_name: string;
    approver_employee_id: string;
    status: 'pending' | 'approved' | 'rejected';
    decided_at: string | null;
    comments: string | null;
  }>;
  created_at: string;
  updated_at: string;
}

export interface DevelopmentPlanQuery {
  search?: string;
  status?: string;
  department?: string;
  page: number;
  page_size: number;
}

export interface DevelopmentPlanCreatePayload {
  employee_id: string;
  owner_manager_id: string;
  review_cycle_id?: string | null;
  title: string;
  description: string;
  effective_from: string;
  effective_to?: string | null;
  goal_ids: string[];
  competency_ids: string[];
}

export interface DevelopmentPlanUpdatePayload {
  title?: string;
  description?: string;
  effective_from?: string;
  effective_to?: string | null;
  status?: DevelopmentPlanRecord['status'];
  goal_ids?: string[];
  competency_ids?: string[];
}

export type EvidenceTargetType = 'key_result' | 'checkin' | 'feedback' | 'review';

export interface EvidenceRecord {
  id: string;
  employee_id: string;
  employee_name: string;
  target_type: EvidenceTargetType;
  linked_record_id: string;
  linked_record_label: string;
  file_name: string;
  uri: string;
  media_type: string;
  size_bytes: number | null;
  sha256: string | null;
  description: string;
  downloadable: boolean;
  created_at: string;
  updated_at: string;
}

export interface EvidenceQuery {
  search?: string;
  target_type?: EvidenceTargetType;
  page: number;
  page_size: number;
}

export type AuditEntityType =
  | 'Employee'
  | 'Manager'
  | 'ReviewCycle'
  | 'Goal'
  | 'KeyResult'
  | 'CheckIn'
  | 'Competency'
  | 'Feedback'
  | 'Review'
  | 'DevelopmentPlan'
  | 'Evidence';

export type AuditOperation =
  | 'INSERT'
  | 'UPDATE'
  | 'DELETE'
  | 'RELATIONSHIP_INSERTED'
  | 'RELATIONSHIP_UPDATED'
  | 'RELATIONSHIP_DELETED';

export interface AuditHistoryRecord {
  event_id: string;
  entity_type: AuditEntityType;
  entity_id: string;
  actor_id: string;
  actor_employee_id: string | null;
  actor_name: string | null;
  actor_attribution_available: boolean;
  operation: AuditOperation;
  recorded_at: string;
  before_data: Record<string, unknown> | null;
  after_data: Record<string, unknown> | null;
}

export interface AuditHistoryQuery {
  entity_type?: AuditEntityType;
  entity_id?: string;
  operation?: AuditOperation;
  date_from?: string;
  date_to?: string;
  page: number;
  page_size: number;
}

export type ExportFormat = 'csv' | 'json' | 'sql' | 'docs';

export interface ExportArtifact {
  file_name: string;
  format: ExportFormat;
  size_bytes: number;
  sha256: string;
  rows?: number | null;
  download_url: string;
}

export interface ExportTableFiles {
  table: string;
  rows: number;
  csv: ExportArtifact;
  json: ExportArtifact;
}

export interface ExportValidationReport {
  total_rows: number;
  duplicate_primary_keys: number;
  foreign_key_columns_validated: number;
  goal_progress_count: number;
  tables: Record<string, number>;
}

export interface DataExportStatus {
  status: 'ready';
  generated_at: number;
  source_database: string;
  preparation_mode: string;
  dataset_sha256: string;
  total_rows: number;
  validation: ExportValidationReport;
  tables: ExportTableFiles[];
  sql: ExportArtifact;
  supplementary: ExportArtifact[];
  documentation: ExportArtifact[];
}

export interface EmployeeRecord {
  id: string;
  manager_id: string | null;
  email: string;
  first_name: string;
  last_name: string;
  job_title: string;
  department: string;
  hire_date: string;
  effective_from: string;
  effective_to: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface ManagerRecord {
  id: string;
  employee_id: string;
  employee_name: string;
  email: string;
  job_title: string;
  department: string;
  report_count: number;
  effective_from: string;
  effective_to: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface KeyResultRecord {
  id: string;
  goal_id: string;
  title: string;
  description: string;
  unit: string;
  target_value: string;
  current_value: string | null;
  weight: string | null;
  effective_from: string;
  effective_to: string | null;
  due_date: string;
  status: string;
  progress: number;
  created_at: string;
  updated_at: string;
}

export interface GoalRecord {
  id: string;
  employee_id: string;
  employee_name: string;
  review_cycle_id: string;
  review_cycle_name: string;
  owner_manager_id: string | null;
  title: string;
  description: string;
  effective_from: string;
  effective_to: string | null;
  due_date: string;
  status: string;
  progress: string;
  key_results: KeyResultRecord[];
  created_at: string;
  updated_at: string;
}

export interface CheckInRecord {
  id: string;
  employee_id: string;
  employee_name: string;
  manager_id: string | null;
  manager_name: string | null;
  review_cycle_id: string | null;
  checkin_date: string;
  notes: string;
  status: string;
  key_result_ids: string[];
  created_at: string;
  updated_at: string;
}

export interface CompetencyRecord {
  id: string;
  name: string;
  category: string;
  description: string;
  effective_from: string;
  effective_to: string | null;
  status: string;
  employee_count: number;
}

export interface EmployeeCompetencyRecord {
  competency_id: string;
  name: string;
  category: string;
  description: string;
  proficiency: string;
  effective_from: string;
  effective_to: string | null;
}

export interface FeedbackRecord {
  id: string;
  author_employee_id: string;
  author_name: string;
  subject_employee_id: string;
  subject_name: string;
  reviewer_relationship: 'manager' | 'peer';
  review_cycle_id: string | null;
  review_cycle_name: string | null;
  content: string;
  visibility: 'private' | 'manager' | 'review_cycle';
  status: 'draft' | 'submitted' | 'withdrawn';
  editable: boolean;
  withdrawable: boolean;
  competencies: Array<{ id: string; name: string; category: string }>;
  created_at: string;
  updated_at: string;
}

export interface ReviewCycleRecord {
  id: string;
  year: number;
  half: 'H1' | 'H2';
  name: string;
  starts_on: string;
  ends_on: string;
  status: 'draft' | 'open' | 'closed' | 'archived';
  review_count: number;
  pending_review_count: number;
  approved_review_count: number;
  created_at: string;
  updated_at: string;
}

export interface ReviewApprovalRecord {
  approver_manager_id: string;
  approver_name: string;
  approver_employee_id: string;
  status: 'pending' | 'approved' | 'rejected';
  decided_at: string | null;
  comments: string | null;
}

export interface ReviewRecord {
  id: string;
  year: number;
  employee_id: string;
  employee_name: string;
  department: string;
  reviewer_manager_id: string;
  reviewer_name: string;
  reviewer_employee_id: string;
  review_cycle_id: string;
  review_cycle_name: string;
  review_cycle_status: ReviewCycleRecord['status'];
  summary: string;
  rating: string | null;
  effective_from: string;
  effective_to: string | null;
  status: 'draft' | 'in_progress' | 'submitted' | 'approved' | 'acknowledged';
  editable: boolean;
  approval_actionable: boolean;
  acknowledgeable: boolean;
  competencies: Array<{ id: string; name: string; category: string }>;
  approvals: ReviewApprovalRecord[];
  created_at: string;
  updated_at: string;
}

async function apiRequest<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers: {
      ...(typeof FormData !== 'undefined' && options.body instanceof FormData
        ? {}
        : { 'Content-Type': 'application/json' }),
      ...(options.headers ?? {}),
    },
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(errorBody.detail || response.statusText || 'Request failed');
  }

  return response.json() as Promise<T>;
}

export async function getHealthStatus(): Promise<HealthStatus> {
  return apiRequest<HealthStatus>('/health');
}

export async function getDashboardAnalytics(): Promise<DashboardAnalytics> {
  return apiRequest<DashboardAnalytics>('/dashboard/analytics');
}

export interface PeopleQuery {
  search?: string;
  status?: string;
  department?: string;
  manager_id?: string;
  page: number;
  page_size: number;
}

function queryString(query: PeopleQuery): string {
  const params = new URLSearchParams();
  Object.entries(query).forEach(([key, value]) => {
    if (value !== undefined && value !== '') params.set(key, String(value));
  });
  return params.toString();
}

export function getEmployees(query: PeopleQuery): Promise<PageResult<EmployeeRecord>> {
  return apiRequest(`/employees?${queryString(query)}`);
}

export function getEmployee(id: string): Promise<EmployeeRecord> {
  return apiRequest(`/employees/${encodeURIComponent(id)}`);
}

export function createEmployee(
  payload: Omit<EmployeeRecord, 'id' | 'created_at' | 'updated_at'>,
): Promise<EmployeeRecord> {
  return apiRequest('/employees', { method: 'POST', body: JSON.stringify(payload) });
}

export function updateEmployee(
  id: string,
  payload: Partial<Omit<EmployeeRecord, 'id' | 'created_at' | 'updated_at'>>,
): Promise<EmployeeRecord> {
  return apiRequest(`/employees/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export function getManagers(query: Omit<PeopleQuery, 'manager_id'>): Promise<PageResult<ManagerRecord>> {
  return apiRequest(`/managers?${queryString(query)}`);
}

export function getManager(id: string): Promise<ManagerRecord> {
  return apiRequest(`/managers/${encodeURIComponent(id)}`);
}

export function createManager(payload: {
  employee_id: string;
  effective_from: string;
  effective_to: string | null;
  status: string;
}): Promise<ManagerRecord> {
  return apiRequest('/managers', { method: 'POST', body: JSON.stringify(payload) });
}

export function updateManager(
  id: string,
  payload: { effective_from?: string; effective_to?: string | null; status?: string },
): Promise<ManagerRecord> {
  return apiRequest(`/managers/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export function getGoals(query: PeopleQuery & { employee_id?: string; review_cycle_id?: string }): Promise<PageResult<GoalRecord>> {
  return apiRequest(`/goals?${queryString(query)}`);
}

export function getDevelopmentPlans(query: DevelopmentPlanQuery): Promise<PageResult<DevelopmentPlanRecord>> {
  return apiRequest(`/development-plans?${queryString(query)}`);
}

export function getDevelopmentPlan(id: string): Promise<DevelopmentPlanRecord> {
  return apiRequest(`/development-plans/${encodeURIComponent(id)}`);
}

export function createDevelopmentPlan(payload: DevelopmentPlanCreatePayload): Promise<DevelopmentPlanRecord> {
  return apiRequest('/development-plans', { method: 'POST', body: JSON.stringify(payload) });
}

export function updateDevelopmentPlan(
  id: string,
  payload: DevelopmentPlanUpdatePayload,
): Promise<DevelopmentPlanRecord> {
  return apiRequest(`/development-plans/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export function decideDevelopmentPlanApproval(
  id: string,
  payload: {
    approver_manager_id: string;
    status: 'approved' | 'rejected';
    comments?: string | null;
  },
): Promise<DevelopmentPlanRecord> {
  return apiRequest(`/development-plans/${encodeURIComponent(id)}/approval`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function getEvidence(query: EvidenceQuery): Promise<PageResult<EvidenceRecord>> {
  return apiRequest(`/evidence?${queryString(query)}`);
}

export function getEvidenceRecord(id: string): Promise<EvidenceRecord> {
  return apiRequest(`/evidence/${encodeURIComponent(id)}`);
}

export function uploadEvidence(payload: {
  employee_id: string;
  target_type: EvidenceTargetType;
  target_id: string;
  description: string;
  file: File;
}): Promise<EvidenceRecord> {
  const form = new FormData();
  form.set('employee_id', payload.employee_id);
  form.set('target_type', payload.target_type);
  form.set('target_id', payload.target_id);
  form.set('description', payload.description);
  form.set('file', payload.file);
  return apiRequest('/evidence', { method: 'POST', body: form });
}

export async function downloadEvidenceFile(id: string): Promise<Blob> {
  const response = await fetch(`${API_BASE_URL}/evidence/${encodeURIComponent(id)}/file`);
  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(errorBody.detail || response.statusText || 'Request failed');
  }
  return response.blob();
}

export function getAuditHistory(query: AuditHistoryQuery): Promise<PageResult<AuditHistoryRecord>> {
  return apiRequest(`/audit-history?${queryString(query)}`);
}

export function getAuditHistoryRecord(eventId: string): Promise<AuditHistoryRecord> {
  return apiRequest(`/audit-history/${encodeURIComponent(eventId)}`);
}

export function getDataExportStatus(): Promise<DataExportStatus> {
  return apiRequest('/data-exports');
}

export function getExportDownloadUrl(artifact: ExportArtifact): string {
  return `${API_BASE_URL}/data-exports/${artifact.format}/${encodeURIComponent(artifact.file_name)}`;
}

export function getGoal(id: string): Promise<GoalRecord> {
  return apiRequest(`/goals/${encodeURIComponent(id)}`);
}

export interface KeyResultPayload {
  title: string;
  description: string;
  unit: string;
  target_value: string;
  current_value: string | null;
  weight: string | null;
  effective_from: string;
  effective_to: string | null;
  due_date: string;
  status: string;
}

export function createGoal(payload: {
  employee_id: string;
  review_cycle_id: string;
  owner_manager_id: string | null;
  title: string;
  description: string;
  effective_from: string;
  effective_to: string | null;
  due_date: string;
  status: string;
  key_results: KeyResultPayload[];
}): Promise<GoalRecord> {
  return apiRequest('/goals', { method: 'POST', body: JSON.stringify(payload) });
}

export function updateGoal(
  id: string,
  payload: Partial<Pick<GoalRecord, 'title' | 'description' | 'owner_manager_id' | 'effective_to' | 'due_date' | 'status'>>,
): Promise<GoalRecord> {
  return apiRequest(`/goals/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify(payload) });
}

export function updateKeyResult(
  id: string,
  payload: Partial<Pick<KeyResultRecord, 'title' | 'description' | 'unit' | 'target_value' | 'current_value' | 'weight' | 'effective_from' | 'effective_to' | 'due_date' | 'status'>>,
): Promise<KeyResultRecord> {
  return apiRequest(`/key-results/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify(payload) });
}

export function getCheckIns(query: PeopleQuery): Promise<PageResult<CheckInRecord>> {
  return apiRequest(`/check-ins?${queryString(query)}`);
}

export function createCheckIn(payload: {
  employee_id: string;
  manager_id: string;
  review_cycle_id: string | null;
  checkin_date: string;
  notes: string;
  status: string;
  key_result_ids: string[];
}): Promise<CheckInRecord> {
  return apiRequest('/check-ins', { method: 'POST', body: JSON.stringify(payload) });
}

export function updateCheckIn(id: string, payload: { status?: string; notes?: string }): Promise<CheckInRecord> {
  return apiRequest(`/check-ins/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify(payload) });
}

export interface CompetencyQuery {
  search?: string;
  category?: string;
  status?: string;
  page: number;
  page_size: number;
}

export function getCompetencies(query: CompetencyQuery): Promise<PageResult<CompetencyRecord>> {
  return apiRequest(`/competencies?${queryString(query)}`);
}

export function getCompetency(id: string): Promise<CompetencyRecord> {
  return apiRequest(`/competencies/${encodeURIComponent(id)}`);
}

export function getEmployeeCompetencies(employeeId: string): Promise<EmployeeCompetencyRecord[]> {
  return apiRequest(`/employees/${encodeURIComponent(employeeId)}/competencies`);
}

export interface FeedbackQuery {
  search?: string;
  status?: string;
  visibility?: string;
  relationship?: 'manager' | 'peer';
  subject_employee_id?: string;
  author_employee_id?: string;
  review_cycle_id?: string;
  page: number;
  page_size: number;
}

export function getFeedback(query: FeedbackQuery): Promise<PageResult<FeedbackRecord>> {
  return apiRequest(`/feedback?${queryString(query)}`);
}

export function getFeedbackRecord(id: string): Promise<FeedbackRecord> {
  return apiRequest(`/feedback/${encodeURIComponent(id)}`);
}

export function createFeedback(payload: {
  author_employee_id: string;
  subject_employee_id: string;
  reviewer_relationship?: 'manager' | 'peer';
  content: string;
  visibility: FeedbackRecord['visibility'];
  status: 'draft' | 'submitted';
  competency_ids: string[];
}): Promise<FeedbackRecord> {
  return apiRequest('/feedback', { method: 'POST', body: JSON.stringify(payload) });
}

export function updateFeedback(
  id: string,
  payload: {
    content?: string;
    visibility?: FeedbackRecord['visibility'];
    status?: FeedbackRecord['status'];
    competency_ids?: string[];
  },
): Promise<FeedbackRecord> {
  return apiRequest(`/feedback/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export function getReviewCycles(query: {
  search?: string;
  status?: string;
  page: number;
  page_size: number;
}): Promise<PageResult<ReviewCycleRecord>> {
  return apiRequest(`/review-cycles?${queryString(query)}`);
}

export function getReviewCycle(id: string): Promise<ReviewCycleRecord> {
  return apiRequest(`/review-cycles/${encodeURIComponent(id)}`);
}

export function createReviewCycle(payload: {
  year: number;
  half: 'H1' | 'H2';
  name: string;
  starts_on: string;
  ends_on: string;
}): Promise<ReviewCycleRecord> {
  return apiRequest('/review-cycles', { method: 'POST', body: JSON.stringify(payload) });
}

export function updateReviewCycle(
  id: string,
  payload: { name?: string; starts_on?: string; ends_on?: string; status?: ReviewCycleRecord['status'] },
): Promise<ReviewCycleRecord> {
  return apiRequest(`/review-cycles/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export function getReviews(query: {
  search?: string;
  status?: string;
  review_cycle_id?: string;
  employee_id?: string;
  reviewer_manager_id?: string;
  page: number;
  page_size: number;
}): Promise<PageResult<ReviewRecord>> {
  return apiRequest(`/reviews?${queryString(query)}`);
}

export function getReview(id: string): Promise<ReviewRecord> {
  return apiRequest(`/reviews/${encodeURIComponent(id)}`);
}

export function createReview(payload: {
  employee_id: string;
  reviewer_manager_id: string;
  review_cycle_id: string;
  summary: string;
  rating: string | null;
  effective_from: string;
  effective_to: string | null;
  competency_ids: string[];
}): Promise<ReviewRecord> {
  return apiRequest('/reviews', { method: 'POST', body: JSON.stringify(payload) });
}

export function updateReview(
  id: string,
  payload: {
    summary?: string;
    rating?: string | null;
    effective_to?: string | null;
    status?: ReviewRecord['status'];
    competency_ids?: string[];
  },
): Promise<ReviewRecord> {
  return apiRequest(`/reviews/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export function decideReviewApproval(
  id: string,
  payload: {
    approver_manager_id: string;
    status: 'approved' | 'rejected';
    comments: string | null;
  },
): Promise<ReviewRecord> {
  return apiRequest(`/reviews/${encodeURIComponent(id)}/approval`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}
