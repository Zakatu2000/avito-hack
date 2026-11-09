import type { Proposal, ServiceRequest, SessionInfo, Workspace } from './types';

export const exampleSessionTrainee: SessionInfo = {
  token: 'test-token-vasya',
  user: {
    id: 'u-1',
    login: 'trainee-vasya',
    displayName: 'Вася Стажёр',
    role: 'trainee',
  },
};

export const exampleSessionOperator: SessionInfo = {
  token: 'test-token-operator',
  user: {
    id: 'u-2',
    login: 'demo-operator',
    displayName: 'Демооператор',
    role: 'operator',
  },
};

export const exampleSessions: SessionInfo[] = [exampleSessionTrainee, exampleSessionOperator];

const task101 = {
  id: 'TSK-101',
  title: 'Настроить CI для учебного сервиса',
  summary: 'Назначена вам · команда «Учебный backend» · наставник: Анна',
  resourceId: 'git.avito.local/trainee/todo-service',
  resourceName: 'todo-service (учебный репозиторий)',
  instruction: {
    title: 'Инструкция «Первый PR»',
    url: 'https://intranet.example/instructions/first-pr',
  },
};

export const exampleWorkspaceInitial: Workspace = {
  user: exampleSessionTrainee.user,
  task: task101,
  effectiveAccess: 'denied',
  request: null,
  nextStep: {
    code: 'ask-assistant',
    title: 'Опишите проблему своими словами',
    items: [
      'Помощник проверит назначение задачи и доступ',
      'Например: «Не могу открыть репозиторий задачи»',
    ],
  },
  aiMode: 'demo',
};

export const exampleProposal: Proposal = {
  id: 'PRP-77',
  resource: 'git.avito.local/trainee/todo-service',
  purpose: 'доступ для выполнения задачи #TSK-101',
  action: 'Создать заявку на доступ (роль: reporter)',
  idempotencyKey: 'idem-REQ-2026-0142',
};

export const exampleRequestPending: ServiceRequest = {
  id: 'REQ-2026-0142',
  status: 'pending',
  resource: 'git.avito.local/trainee/todo-service',
  purpose: 'доступ для выполнения задачи #TSK-101',
};

export const exampleRequestApproved: ServiceRequest = {
  ...exampleRequestPending,
  status: 'approved',
};

export const exampleRequestRejected: ServiceRequest = {
  ...exampleRequestPending,
  status: 'rejected',
};

export const exampleWorkspacePending: Workspace = {
  ...exampleWorkspaceInitial,
  request: exampleRequestPending,
  nextStep: {
    code: 'wait-decision',
    title: 'Заявка на согласовании',
    items: ['Решение по заявке и выдача права — два разных шага', 'Обновите состояние, пока ждёте'],
  },
};

export const exampleWorkspaceApprovedNoAccess: Workspace = {
  ...exampleWorkspaceInitial,
  request: exampleRequestApproved,
  effectiveAccess: 'unknown',
  nextStep: {
    code: 'wait-access',
    title: 'Ждём выдачу права',
    items: ['Заявку одобрили, право на ресурсе пока не подтверждено', 'Обновите состояние чуть позже'],
  },
};

export const exampleWorkspaceGranted: Workspace = {
  ...exampleWorkspaceInitial,
  request: exampleRequestApproved,
  effectiveAccess: 'granted',
  nextStep: {
    code: 'return-to-task',
    title: 'Следующий шаг по задаче',
    items: [
      'Склонируйте репозиторий todo-service',
      'Откройте инструкцию «Первый PR»',
      'Создайте ветку feat/<имя> и начните задачу',
    ],
  },
};

export const exampleWorkspaceGrantedDirect: Workspace = {
  ...exampleWorkspaceInitial,
  request: null,
  effectiveAccess: 'granted',
  nextStep: {
    code: 'return-to-task',
    title: 'Следующий шаг по задаче',
    items: [
      'Склонируйте репозиторий todo-service',
      'Откройте инструкцию «Первый PR»',
      'Создайте ветку feat/<имя> и начните задачу',
    ],
  },
};

export const exampleWorkspaceRejected: Workspace = {
  ...exampleWorkspaceInitial,
  request: exampleRequestRejected,
  nextStep: {
    code: 'ask-mentor',
    title: 'Заявка отклонена',
    items: ['Причина указана в заявке', 'Уточните детали у наставника — контакт в описании задачи'],
  },
};

export const exampleWorkspaceEmpty: Workspace = {
  user: exampleSessionTrainee.user,
  task: null,
  effectiveAccess: 'unknown',
  request: null,
  nextStep: null,
  aiMode: 'demo',
};

export const exampleWorkspaceOperator: Workspace = {
  user: exampleSessionOperator.user,
  task: null,
  effectiveAccess: 'unknown',
  request: null,
  nextStep: null,
  aiMode: 'demo',
};
