// Small centralized fetching hooks, each wired to live WS events so views
// re-fetch (debounced) when the backend emits a relevant change.
import { api, type AccountsFilter } from '../services/api';
import { useEvents } from '../services/useEvents';
import { useAsync, useDebouncedCallback } from './useAsync';

export function useDashboard() {
  const state = useAsync(() => api.getDashboard(), []);
  const refetch = useDebouncedCallback(state.refetch, 500);
  useEvents(
    ['account.*', 'robot.*', 'recovery.*', 'alert.*', 'workflow.step'],
    () => refetch(),
  );
  return state;
}

export function useAccounts(filter: AccountsFilter) {
  const key = JSON.stringify(filter);
  const state = useAsync(() => api.getAccounts(filter), [key]);
  const refetch = useDebouncedCallback(state.refetch, 500);
  useEvents(['account.*', 'robot.*', 'recovery.*'], () => refetch());
  return state;
}

export function useAccount(id: number) {
  const state = useAsync(() => api.getAccount(id), [id]);
  const refetch = useDebouncedCallback(state.refetch, 400);
  useEvents(['account.*', 'robot.*', 'recovery.*', 'alert.*'], (msg) => {
    if (msg.payload?.account_id == null || msg.payload.account_id === id) refetch();
  });
  return state;
}

export function usePropFirms() {
  const state = useAsync(() => api.getPropFirms(), []);
  useEvents(['account.created', 'account.removed'], () => state.refetch());
  return state;
}

export function usePropFirm(id: number) {
  const state = useAsync(() => api.getPropFirm(id), [id]);
  const refetch = useDebouncedCallback(state.refetch, 500);
  useEvents(['account.*', 'robot.*'], () => refetch());
  return state;
}

export function useStrategies() {
  const state = useAsync(() => api.getStrategies(), []);
  const refetch = useDebouncedCallback(state.refetch, 500);
  useEvents(['account.*', 'robot.*'], () => refetch());
  return state;
}

export function useMarkets() {
  return useAsync(() => api.getMarkets(), []);
}

export function useAttention() {
  const state = useAsync(() => api.getAttention(), []);
  const refetch = useDebouncedCallback(state.refetch, 500);
  useEvents(['account.*', 'robot.*', 'recovery.*', 'alert.*'], () => refetch());
  return state;
}

export function usePlatforms() {
  return useAsync(() => api.getPlatforms(), []);
}
