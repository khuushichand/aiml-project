import { api } from '@/lib/api-client';
import type {
  RouterAnalyticsBreakdownsResponse,
  RouterAnalyticsMetaResponse,
  RouterAnalyticsQuery,
  RouterAnalyticsStatusResponse,
} from '@/lib/router-analytics-types';

const toQueryParams = (query: RouterAnalyticsQuery = {}): Record<string, string> => {
  const params: Record<string, string> = {};
  if (query.range) params.range = query.range;
  if (query.orgId !== undefined) params.org_id = String(query.orgId);
  if (query.provider) params.provider = query.provider;
  if (query.model) params.model = query.model;
  if (query.tokenId !== undefined) params.token_id = String(query.tokenId);
  if (query.granularity) params.granularity = query.granularity;
  return params;
};

export async function getRouterAnalyticsStatus(query: RouterAnalyticsQuery = {}): Promise<RouterAnalyticsStatusResponse> {
  return await api.getRouterAnalyticsStatus(toQueryParams(query)) as RouterAnalyticsStatusResponse;
}

export async function getRouterAnalyticsStatusBreakdowns(
  query: RouterAnalyticsQuery = {}
): Promise<RouterAnalyticsBreakdownsResponse> {
  return await api.getRouterAnalyticsStatusBreakdowns(toQueryParams(query)) as RouterAnalyticsBreakdownsResponse;
}

export async function getRouterAnalyticsMeta(query: Pick<RouterAnalyticsQuery, 'orgId'> = {}): Promise<RouterAnalyticsMetaResponse> {
  return await api.getRouterAnalyticsMeta(toQueryParams({ orgId: query.orgId })) as RouterAnalyticsMetaResponse;
}
