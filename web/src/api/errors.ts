export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export class SessionExpiredError extends Error {
  constructor() {
    super('Тестовая сессия истекла');
    this.name = 'SessionExpiredError';
  }
}

export class NetworkError extends Error {
  constructor() {
    super('Не получилось связаться с сервером');
    this.name = 'NetworkError';
  }
}
