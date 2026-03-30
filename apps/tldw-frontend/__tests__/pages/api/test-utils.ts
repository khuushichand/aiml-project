import type { NextApiRequest, NextApiResponse } from 'next';

type CreateApiRequestOptions = {
  method?: string;
  url?: string;
  headers?: Record<string, string>;
  body?: unknown;
  query?: Record<string, string | string[]>;
};

type HeaderValue = string | string[];

const parseCookieHeader = (value?: string): Record<string, string> => {
  if (!value) {
    return {};
  }

  return value
    .split(';')
    .map((chunk) => chunk.trim())
    .filter(Boolean)
    .reduce<Record<string, string>>((acc, chunk) => {
      const [rawName, ...rawValue] = chunk.split('=');
      if (!rawName) {
        return acc;
      }

      acc[rawName] = decodeURIComponent(rawValue.join('=') || '');
      return acc;
    }, {});
};

export type MockApiResponse = NextApiResponse & {
  statusCode: number;
  body: unknown;
  headers: Record<string, HeaderValue>;
};

export const createApiRequest = (
  options: CreateApiRequestOptions = {},
): NextApiRequest => {
  const normalizedHeaders = Object.fromEntries(
    Object.entries(options.headers || {}).map(([key, value]) => [
      key.toLowerCase(),
      value,
    ]),
  );

  return {
    method: options.method || 'GET',
    url: options.url || '/api/test',
    headers: normalizedHeaders,
    body: options.body,
    query: options.query || {},
    cookies: parseCookieHeader(normalizedHeaders.cookie),
  } as unknown as NextApiRequest;
};

export const createApiResponse = (): MockApiResponse => {
  const headers: Record<string, HeaderValue> = {};

  const response = {
    statusCode: 200,
    body: undefined,
    headers,
    status(code: number) {
      response.statusCode = code;
      return response;
    },
    setHeader(name: string, value: HeaderValue) {
      headers[name.toLowerCase()] = value;
      return response;
    },
    getHeader(name: string) {
      return headers[name.toLowerCase()];
    },
    getHeaders() {
      return headers;
    },
    json(payload: unknown) {
      response.body = payload;
      return response;
    },
    send(payload: unknown) {
      response.body = payload;
      return response;
    },
    end(payload?: unknown) {
      response.body = payload;
      return response;
    },
  };

  return response as unknown as MockApiResponse;
};
