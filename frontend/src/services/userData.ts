import apiClient from './api';

/**
 * GDPR access/portability/erasure, from the student's side.
 *
 * These exist as UI-reachable actions on purpose: a right that can only be
 * exercised by hand-crafting an HTTP request is not a right a 12-year-old
 * (or their parent) actually has.
 */

/** Downloads everything the platform holds about the caller as a JSON file. */
export async function downloadMyData(): Promise<void> {
  const response = await apiClient.get('/auth/me/export', { responseType: 'blob' });

  const url = URL.createObjectURL(new Blob([response.data], { type: 'application/json' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = 'smartnvo-moite-danni.json';
  document.body.appendChild(link);
  link.click();
  link.remove();
  // Revoked on the next tick rather than immediately: Safari cancels an
  // in-flight download if the object URL disappears in the same frame.
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export interface DeleteAccountResult {
  deleted: boolean;
  removed_rows: Record<string, number>;
}

/** Irreversible. The caller's token stops resolving the moment this returns. */
export async function deleteMyAccount(): Promise<DeleteAccountResult> {
  const response = await apiClient.delete<DeleteAccountResult>('/auth/me');
  return response.data;
}
