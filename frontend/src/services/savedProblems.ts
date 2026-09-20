import apiClient from './api';

export type SavedProblemSource = 'exercise' | 'nvo';

export type SavedProblemAnswerType = 'multiple_choice' | 'numeric' | 'algebra' | 'open';

export interface SavedProblemOption {
  key: string;
  text: string;
}

export interface SavedProblemOrigin {
  // kind === 'exercise'
  lesson_id?: number;
  lesson_title?: string;
  difficulty?: string;
  // kind === 'nvo'
  exam_id?: string;
  question_number?: number;
  module?: number;
  topic?: string;
}

/**
 * One shape for both sources, so the review page needs a single renderer.
 * Everything but `question` is optional — a snapshot written by an older build
 * must still render.
 */
export interface SavedProblemSnapshot {
  kind: SavedProblemSource;
  question: string;
  answer_type: SavedProblemAnswerType;
  options?: SavedProblemOption[] | null;
  correct_answer?: string | string[] | null;
  solution?: string | null;
  diagram?: { type: string; config: Record<string, unknown> } | null;
  user_answer?: string | null;
  origin: SavedProblemOrigin;
}

export interface SavedProblem {
  id: number;
  source: SavedProblemSource;
  source_ref: string;
  snapshot: SavedProblemSnapshot;
  created_at: string;
}

export function exerciseRef(exerciseId: number): string {
  return String(exerciseId);
}

export function nvoRef(examId: string, questionNumber: number): string {
  return `${examId}:${questionNumber}`;
}

export function refKey(source: SavedProblemSource, sourceRef: string): string {
  return `${source}:${sourceRef}`;
}

export async function listSavedProblems(params?: {
  limit?: number;
  source?: SavedProblemSource;
}): Promise<SavedProblem[]> {
  const response = await apiClient.get('/saved-problems', { params });
  return Array.isArray(response.data) ? response.data : [];
}

export async function listSavedRefs(): Promise<Record<string, number>> {
  const response = await apiClient.get('/saved-problems/refs');
  return response.data?.refs ?? {};
}

export async function saveProblem(input: {
  source: SavedProblemSource;
  source_ref: string;
  snapshot: SavedProblemSnapshot;
}): Promise<SavedProblem> {
  const response = await apiClient.post('/saved-problems', input);
  return response.data;
}

export async function deleteSavedProblem(id: number): Promise<void> {
  await apiClient.delete(`/saved-problems/${id}`);
}
