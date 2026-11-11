import { z } from 'zod'

/* ---------- Пользователи и роли ---------- */

export const RoleSchema = z.enum(['intern', 'mentor', 'lead'])
export type Role = z.infer<typeof RoleSchema>

export const UserSchema = z.object({
  id: z.string(),
  name: z.string(),
  role: RoleSchema,
  roleLabel: z.string(),
  team: z.string(),
  initials: z.string(),
})
export type User = z.infer<typeof UserSchema>

/* ---------- Чек-лист адаптации ---------- */

export const ItemStatusSchema = z.enum(['not_started', 'in_progress', 'pending_approval', 'done'])
export type ItemStatus = z.infer<typeof ItemStatusSchema>

export const ChecklistItemSchema = z.object({
  id: z.string(),
  title: z.string(),
  description: z.string(),
  nextStep: z.string(),
  requiresApproval: z.boolean(),
  status: ItemStatusSchema,
  deadline: z.string().nullable(),
  actionLink: z.string().nullable(),
})
export type ChecklistItem = z.infer<typeof ChecklistItemSchema>

export const ChecklistStageSchema = z.object({
  id: z.string(),
  title: z.string(),
  period: z.string(),
  items: z.array(ChecklistItemSchema),
})
export type ChecklistStage = z.infer<typeof ChecklistStageSchema>

export const ChecklistSchema = z.array(ChecklistStageSchema)
export type Checklist = z.infer<typeof ChecklistSchema>

/* ---------- Запросы (отгул / доступ) ---------- */

export const RequestKindSchema = z.enum(['leave', 'access'])
export type RequestKind = z.infer<typeof RequestKindSchema>

export const RequestStatusSchema = z.enum(['draft', 'sent', 'approving', 'approved', 'rejected'])
export type RequestStatus = z.infer<typeof RequestStatusSchema>

export const LeaveReasonSchema = z.enum(['vacation', 'sick', 'personal', 'other'])
export type LeaveReason = z.infer<typeof LeaveReasonSchema>

export const ISODate = z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'Формат даты ГГГГ-ММ-ДД')

export const LeavePayloadSchema = z.object({
  kind: z.literal('leave'),
  startDate: ISODate,
  endDate: ISODate,
  reason: LeaveReasonSchema,
  comment: z.string().max(300).optional(),
})

export const AccessPayloadSchema = z.object({
  kind: z.literal('access'),
  system: z.string().min(1),
  justification: z.string().min(10, 'Укажи задачу — минимум 10 символов').max(300),
  durationDays: z.number().int().min(1).max(365),
})

export const RequestPayloadSchema = z.discriminatedUnion('kind', [LeavePayloadSchema, AccessPayloadSchema])
export type RequestPayload = z.infer<typeof RequestPayloadSchema>

export const HistoryEntrySchema = z.object({
  at: z.string(),
  status: z.string(),
  by: z.string(),
  comment: z.string().optional(),
})
export type HistoryEntry = z.infer<typeof HistoryEntrySchema>

export const RequestSchema = z.object({
  id: z.string(),
  kind: RequestKindSchema,
  authorId: z.string(),
  authorName: z.string(),
  status: RequestStatusSchema,
  createdAt: z.string(),
  updatedAt: z.string(),
  approvers: z.array(z.string()),
  payload: RequestPayloadSchema,
  history: z.array(HistoryEntrySchema),
})
export type Request = z.infer<typeof RequestSchema>

export const LeaveRequestInputSchema = LeavePayloadSchema.omit({ kind: true }).extend({
  saveDraft: z.boolean().optional(),
})
export type LeaveRequestInput = z.infer<typeof LeaveRequestInputSchema>

export const AccessRequestInputSchema = AccessPayloadSchema.omit({ kind: true }).extend({
  saveDraft: z.boolean().optional(),
})
export type AccessRequestInput = z.infer<typeof AccessRequestInputSchema>

/* ---------- Контакты ---------- */

export const ContactSchema = z.object({
  id: z.string(),
  name: z.string(),
  role: z.string(),
  helpsWith: z.array(z.string()),
  channel: z.string(),
  responseTime: z.string(),
  tone: z.enum(['green', 'blue', 'purple', 'red', 'gray']),
})
export type Contact = z.infer<typeof ContactSchema>
export const ContactListSchema = z.array(ContactSchema)

/* ---------- База знаний ---------- */

export const KbArticleSchema = z.object({
  id: z.string(),
  title: z.string(),
  tags: z.array(z.string()),
  duration: z.string(),
  updated: z.string(),
  steps: z.array(z.string()),
})
export type KbArticle = z.infer<typeof KbArticleSchema>
export const KbListSchema = z.array(KbArticleSchema)

/* ---------- Метрики ---------- */

export const RangeSchema = z.object({ min: z.number(), max: z.number() })
export const MetricsSchema = z.object({
  mentorHoursSaved: z.object({
    baseline: RangeSchema,
    target: RangeSchema,
    current: z.number(),
  }),
  questionsWithoutMentorShare: z.number(),
  timeToFirstTaskDays: z.object({ before: z.number(), current: z.number() }),
  internsOnTrackShare: z.number(),
})
export type Metrics = z.infer<typeof MetricsSchema>

/* ---------- Вид наставника/руководителя ---------- */

export const InternSummarySchema = z.object({
  user: UserSchema,
  progress: z.object({
    done: z.number(),
    total: z.number(),
    percent: z.number(),
  }),
  nextStepTitle: z.string().nullable(),
})
export type InternSummary = z.infer<typeof InternSummarySchema>
export const InternListSchema = z.array(InternSummarySchema)

/* ---------- Чат ---------- */

export const ChatActionSchema = z.object({
  id: z.string(),
  label: z.string(),
  kind: z.enum(['navigate', 'contact']),
  target: z.string().nullable(),
})
export type ChatAction = z.infer<typeof ChatActionSchema>

export const ChatReplySchema = z.object({
  intentId: z.string(),
  text: z.string(),
  actions: z.array(ChatActionSchema),
})
export type ChatReply = z.infer<typeof ChatReplySchema>

/* ---------- Ошибки API ---------- */

export const ApiErrorBodySchema = z.object({
  message: z.string(),
  code: z.string(),
})
