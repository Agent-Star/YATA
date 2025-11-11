export class ApiError extends Error {
  constructor(message, { code, status } = {}) {
    super(message);
    this.name = 'ApiError';
    this.code = code || 'UNKNOWN_ERROR';
    this.status = status || 500;
  }
}

const DEFAULT_HEADERS = {
  'Content-Type': 'application/json',
};

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || '';

export async function apiRequest(path, { headers, body, ...options } = {}) {
  const url = `${API_BASE_URL}${path}`;
  const requestInit = {
    credentials: 'include',
    ...options,
    headers: {
      ...DEFAULT_HEADERS,
      ...headers,
    },
  };

  if (body && !(body instanceof FormData)) {
    requestInit.body = JSON.stringify(body);
  } else if (body) {
    // Allow form-data without overriding headers
    delete requestInit.headers['Content-Type'];
    requestInit.body = body;
  }

  const response = await fetch(url, requestInit);
  const contentType = response.headers.get('content-type') || '';
  const isJson = contentType.includes('application/json');
  const data = isJson ? await response.json().catch(() => null) : null;

  if (!response.ok) {
    const message = data?.message || `Request to ${path} failed`;
    const code = data?.code || 'API_ERROR';
    throw new ApiError(message, { code, status: response.status });
  }

  return data;
}

export async function streamRequest(path, { headers, body, signal, ...options } = {}) {
  const url = `${API_BASE_URL}${path}`;
  const controller = new AbortController();

  if (signal) {
    if (signal.aborted) {
      controller.abort();
    } else {
      signal.addEventListener('abort', () => controller.abort(), { once: true });
    }
  }

  const requestInit = {
    credentials: 'include',
    ...options,
    signal: controller.signal,
    headers: {
      ...DEFAULT_HEADERS,
      ...headers,
    },
  };

  if (body && !(body instanceof FormData)) {
    requestInit.body = JSON.stringify(body);
  } else if (body) {
    delete requestInit.headers['Content-Type'];
    requestInit.body = body;
  }

  const response = await fetch(url, requestInit);

  if (!response.ok) {
    const contentType = response.headers.get('content-type') || '';
    const isJson = contentType.includes('application/json');
    const data = isJson ? await response.json().catch(() => null) : null;
    const message = data?.message || `Request to ${path} failed`;
    const code = data?.code || 'API_ERROR';
    throw new ApiError(message, { code, status: response.status });
  }

  return {
    response,
    abort: () => controller.abort(),
  };
}
