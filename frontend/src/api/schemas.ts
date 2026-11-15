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

export const NewRequestKindSchema = z.enum(['technical_support', 'mentor_consultation', 'learning_request'])
export type NewRequestKind = z.infer<typeof NewRequestKindSchema>
export const RequestKindSchema = z.enum(['leave', 'access', ...NewRequestKindSchema.options])
export type RequestKind = z.infer<typeof RequestKindSchema>

export const RequestStatusSchema = z.enum(['draft', 'sent', 'approving', 'approved', 'rejected',
  'in_progress', 'resolved', 'closed', 'awaiting_confirmation', 'scheduled', 'completed'])
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

export const TrackSchema = z.enum(['backend', 'analytics', 'marketing'])
export const SupportCategorySchema = z.enum(['environment', 'software', 'network', 'git', 'other'])
export const PrioritySchema = z.enum(['low', 'normal', 'high'])
const related = { taskId: z.string().optional() }
const SupportFields = z.object({
  category: SupportCategorySchema, title: z.string().trim().min(1).max(200),
  description: z.string().trim().min(1).max(2000), priority: PrioritySchema, ...related,
})
const ConsultationFields = z.object({
  topic: z.string().trim().min(1).max(200), description: z.string().trim().min(1).max(2000),
  preferredAt: z.string().datetime({ offset: true }), ...related,
})
const LearningFields = z.object({
  topic: z.string().trim().min(1).max(200), track: TrackSchema, reason: z.string().trim().min(1).max(2000), ...related,
})
export const NewRequestInputSchemas = {
  technical_support: SupportFields,
  mentor_consultation: ConsultationFields,
  learning_request: LearningFields,
}
export const RequestPayloadSchema = z.discriminatedUnion('kind', [
  LeavePayloadSchema, AccessPayloadSchema,
  SupportFields.partial().extend({ kind: z.literal('technical_support') }),
  ConsultationFields.partial().extend({ kind: z.literal('mentor_consultation') }),
  LearningFields.partial().extend({ kind: z.literal('learning_request') }),
])
export const RequestOperationSchema = z.enum(['edit', 'send', 'claim', 'resolve', 'close', 'reopen',
  'schedule', 'propose', 'accept', 'counter', 'complete', 'recommend'])
export type RequestOperation = z.infer<typeof RequestOperationSchema>
export type RequestPayload = z.infer<typeof RequestPayloadSchema>

export const HistoryEntrySchema = z.object({
  at: z.string(),
  scheduledAt: z.string().optional(),
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
  taskId: z.string().nullish(),
  assignee: z.object({ id: z.string(), name: z.string() }).nullish(),
  result: z.object({ text: z.string(), url: z.string().nullable() }).nullish(),
  scheduledAt: z.string().nullish(),
  proposedAt: z.string().nullish(),
  allowedActions: z.array(RequestOperationSchema).optional(),
})
export type Request = z.infer<typeof RequestSchema>

export const LeaveRequestInputSchema = LeavePayloadSchema.omit({ kind: true }).extend({
  saveDraft: z.boolean().optional(),
})
export type LeaveRequestInput = z.infer<typeof LeaveRequestInputSchema>

export const AccessRequestInputSchema = AccessPayloadSchema.omit({ kind: true }).extend({
  taskId: z.string().optional(),
  saveDraft: z.boolean().optional(),
})
export type AccessRequestInput = z.infer<typeof AccessRequestInputSchema>

/* ---------- Контакты ---------- */

export const ContactRoleSchema = z.enum(['mentor', 'lead', 'hr', 'curator'])
export type ContactRole = z.infer<typeof ContactRoleSchema>

export const ContactSchema = z.object({
  roleKey: ContactRoleSchema.optional(),
  source: z.enum(['team', 'demo']).optional(),
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
  firstTaskStatus: z.enum(['unassigned', 'assigned', 'reported', 'confirmed']).optional(),
})
export type InternSummary = z.infer<typeof InternSummarySchema>
export const InternListSchema = z.array(InternSummarySchema)

export const PendingItemSchema = z.object({
  userId: z.string(),
  userName: z.string(),
  itemId: z.string(),
  title: z.string(),
  nextStep: z.string(),
})
export type PendingItem = z.infer<typeof PendingItemSchema>
export const PendingItemListSchema = z.array(PendingItemSchema)

/* ---------- Чат ---------- */

export const ChatActionSchema = z.object({
  id: z.string(),
  label: z.string(),
  kind: z.enum(['navigate', 'contact']),
  target: z.string().nullable(),
})
export type ChatAction = z.infer<typeof ChatActionSchema>

export const ChatConfigSchema = z.object({ aiMode: z.enum(['demo', 'live']) })
export const KnowledgeHitSchema = z.object({
  chunkId: z.string(), title: z.string(), section: z.string(), snippet: z.string(),
  url: z.string().nullable(), sourceLocator: z.string().nullable(), synthetic: z.boolean(),
  sourceType: z.string(), sourceStatus: z.string(), estimatedMinutes: z.number().nullable(),
  difficulty: z.string().nullable(),
})
export type KnowledgeHit = z.infer<typeof KnowledgeHitSchema>

export const ChatReplySchema = z.object({
  intentId: z.string(),
  text: z.string(),
  actions: z.array(ChatActionSchema),
  aiMode: ChatConfigSchema.shape.aiMode.optional(),
  answerMethod: z.enum(['rules', 'model']).optional(),
  sources: z.array(KnowledgeHitSchema).optional(),
  messageId: z.string().optional(),
  conversationId: z.string().optional(),
})
export type ChatReply = z.infer<typeof ChatReplySchema>

export const ChatSummarySchema = z.object({
  id: z.string(),
  title: z.string(),
  createdAt: z.string(),
  updatedAt: z.string(),
})
export type ChatSummary = z.infer<typeof ChatSummarySchema>
export const ChatListSchema = z.array(ChatSummarySchema)

export const ChatHistoryMessageSchema = z.object({
  id: z.union([z.number(), z.string()]),
  role: z.enum(['user', 'bot']),
  text: z.string(),
  actions: z.array(ChatActionSchema).optional(),
  sources: z.array(KnowledgeHitSchema).optional(),
  answerMethod: ChatReplySchema.shape.answerMethod,
  messageId: z.string().optional(),
  feedback: z.enum(['resolved', 'mentor']).optional(),
})
export type ChatHistoryMessage = z.infer<typeof ChatHistoryMessageSchema>
export const ChatHistorySchema = z.array(ChatHistoryMessageSchema)

/* ---------- Ошибки API ---------- */

export const ApiErrorBodySchema = z.object({
  message: z.string(),
  code: z.string(),
})

export type ZodTypeLike<T> = z.ZodType<T>

export const UserListSchema = z.array(UserSchema)
export const RequestListSchema = z.array(RequestSchema)

const BlockerSchema = z.object({ reason: z.string(), action: z.string() })
export const PlanItemSchema = ChecklistItemSchema.extend({
  stage: z.number(), stageLabel: z.string(), sources: z.array(z.string()), canWork: z.boolean(),
  origin: z.enum(['portal', 'catalog', 'assignment']),
  blockers: z.array(BlockerSchema),
  requests: z.array(z.object({ id: z.string(), kind: RequestKindSchema, status: RequestStatusSchema })),
  completionCriteria: z.string().optional(),
  completionPolicy: z.string().optional(),
  startedAt: z.string().nullish(), completedAt: z.string().nullish(),
})
export type PlanItem = z.infer<typeof PlanItemSchema>
export const AdaptationPlanSchema = z.object({
  track: TrackSchema, stage: z.string(),
  items: z.array(PlanItemSchema),
  quickStart: z.array(z.object({ id: z.string(), title: z.string(), items: z.array(PlanItemSchema), done: z.boolean() })),
  blockers: z.array(BlockerSchema.extend({ itemId: z.string(), title: z.string() })),
  nextStep: PlanItemSchema.nullable(),
  firstTask: z.object({ code: z.string(), opened: z.boolean(), reported: z.boolean(), confirmed: z.boolean() }).nullable(),
})
export const OpenFirstTaskSchema = z.object({ code: z.string(), title: z.string(), description: z.string(), demo: z.boolean() })
const MeasurementSchema = z.object({ value: z.number().nullable(), sampleSize: z.number() })
export const AdaptationMetricsSchema = z.object({
  origin: z.literal('measured'), firstTaskMinutes: MeasurementSchema, blockerMinutes: MeasurementSchema,
  requestMinutes: MeasurementSchema, withoutMentor: MeasurementSchema, quickStart: MeasurementSchema,
  manualActionsAvoided: MeasurementSchema,
})
