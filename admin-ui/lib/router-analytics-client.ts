import { api } from '@/lib/api-client';
import type {
  RouterAnalyticsAccessResponse,
  RouterAnalyticsBreakdownsResponse,
  RouterAnalyticsConversationsResponse,
  RouterAnalyticsLogResponse,
  RouterAnalyticsMetaResponse,
  RouterAnalyticsModelsResponse,
  RouterAnalyticsNetworkResponse,
  RouterAnalyticsProvidersResponse,
  RouterAnalyticsQuotaResponse,
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

export async function getRouterAnalyticsQuota(query: RouterAnalyticsQuery = {}): Promise<RouterAnalyticsQuotaResponse> {
  return await api.getRouterAnalyticsQuota(toQueryParams(query)) as RouterAnalyticsQuotaResponse;
}

export async function getRouterAnalyticsProviders(query: RouterAnalyticsQuery = {}): Promise<RouterAnalyticsProvidersResponse> {
  return await api.getRouterAnalyticsProviders(toQueryParams(query)) as RouterAnalyticsProvidersResponse;
}

export async function getRouterAnalyticsAccess(query: RouterAnalyticsQuery = {}): Promise<RouterAnalyticsAccessResponse> {
  return await api.getRouterAnalyticsAccess(toQueryParams(query)) as RouterAnalyticsAccessResponse;
}

export async function getRouterAnalyticsNetwork(query: RouterAnalyticsQuery = {}): Promise<RouterAnalyticsNetworkResponse> {
  return await api.getRouterAnalyticsNetwork(toQueryParams(query)) as RouterAnalyticsNetworkResponse;
}

export async function getRouterAnalyticsModels(query: RouterAnalyticsQuery = {}): Promise<RouterAnalyticsModelsResponse> {
  return await api.getRouterAnalyticsModels(toQueryParams(query)) as RouterAnalyticsModelsResponse;
}

export async function getRouterAnalyticsConversations(
  query: RouterAnalyticsQuery = {}
): Promise<RouterAnalyticsConversationsResponse> {
  return await api.getRouterAnalyticsConversations(toQueryParams(query)) as RouterAnalyticsConversationsResponse;
}

export async function getRouterAnalyticsLog(query: RouterAnalyticsQuery = {}): Promise<RouterAnalyticsLogResponse> {
  return await api.getRouterAnalyticsLog(toQueryParams(query)) as RouterAnalyticsLogResponse;
}

export async function getRouterAnalyticsMeta(query: Pick<RouterAnalyticsQuery, 'orgId'> = {}): Promise<RouterAnalyticsMetaResponse> {
  return await api.getRouterAnalyticsMeta(toQueryParams({ orgId: query.orgId })) as RouterAnalyticsMetaResponse;
}
