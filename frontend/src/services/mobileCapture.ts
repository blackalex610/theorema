import { fileToJpegFile } from '../utils/imageCapture';
import apiClient from './api';

export interface MobileUploadResponse {
  file_name: string;
  file_url: string;
  content_type: string | null;
  size_bytes: number;
  uploaded_at: string;
}

export interface UploadEvent extends MobileUploadResponse {
  channel_id: string;
  problem_number?: number | null;
}

export interface TaskGradeRequest {
  channel_id: string;
  problem_number: number;
  a: number;
  b: number;
  correct_xy: string;
  student_answer: string;
  photo_url?: string | null;
}

export interface TaskContext {
  channel_id: string;
  problem_number: number;
  a: number;
  b: number;
  correct_xy: string;
  updated_at: string;
  statement?: string | null;
  /** The latest grade for this task (set by the grading endpoints). */
  last_grade?: TaskGradeResult | null;
}

export interface TaskGradeResult {
  channel_id: string;
  problem_number: number;
  submitted_answer: string;
  is_correct: boolean;
  score: number;
  feedback: string;
  graded_at: string;
  file_url?: string | null;
}

export const uploadMobilePhoto = async (file: File, channelId: string, problemNumber?: number): Promise<MobileUploadResponse> => {
  // Raw camera files (12 MP, often HEIC) exceed the hosting platform's
  // request-size limit and aren't readable by the grader; always send a
  // downscaled JPEG.
  const jpeg = await fileToJpegFile(file);
  const formData = new FormData();
  formData.append('file', jpeg);
  formData.append('channel_id', channelId);
  if (problemNumber !== undefined) {
    formData.append('problem_number', String(problemNumber));
  }

  const response = await apiClient.post<MobileUploadResponse>('/mobile/uploads', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });

  return response.data;
};

export const getLatestMobileUploads = async (channelId: string, limit = 20): Promise<UploadEvent[]> => {
  const response = await apiClient.get<UploadEvent[]>('/mobile/uploads/latest', {
    params: { channel_id: channelId, limit },
  });
  return response.data;
};

export const submitTaskGrade = async (payload: TaskGradeRequest): Promise<TaskGradeResult> => {
  const response = await apiClient.post<TaskGradeResult>('/mobile/tasks/grade', payload);
  return response.data;
};

export const submitTaskGradeFromPhoto = async (payload: {
  channel_id: string;
  file_name: string;
  problem_number: number;
}): Promise<TaskGradeResult> => {
  const response = await apiClient.post<TaskGradeResult>('/mobile/tasks/grade-photo', payload);
  return response.data;
};

export const setTaskContext = async (payload: {
  channel_id: string;
  problem_number: number;
  a: number;
  b: number;
  correct_xy: string;
  statement?: string | null;
}): Promise<TaskContext> => {
  const response = await apiClient.post<TaskContext>('/mobile/tasks/context', {
    ...payload,
    updated_at: new Date().toISOString(),
  });
  return response.data;
};

export const clearChannelHistory = async (channelId: string): Promise<void> => {
  await apiClient.delete('/mobile/channel/history', { params: { channel_id: channelId } });
};

export const getTaskContexts = async (channelId: string): Promise<TaskContext[]> => {
  const response = await apiClient.get<TaskContext[]>('/mobile/tasks/contexts', {
    params: { channel_id: channelId },
  });
  return response.data;
};

export type ChannelStatus = 'live' | 'error';

/**
 * Follows a photo channel by polling: new uploads from /mobile/uploads/latest
 * and new grades from /mobile/tasks/contexts (each task keeps its latest).
 *
 * This replaced an EventSource on /mobile/uploads/stream. The server kept
 * stream subscribers in one process's memory, so on serverless hosting an
 * event only reached a desktop connected to that same instance, and every
 * open stream kept a function running. Polling reads durable storage and
 * works from any instance.
 *
 * Whatever already exists at the first poll is taken as seen, not reported
 * (pages load their initial list themselves). Polling pauses while the tab
 * is hidden. Returns a function that stops it.
 */
export const watchMobileChannel = (
  channelId: string,
  handlers: {
    onUpload?: (event: UploadEvent) => void;
    onGrade?: (grade: TaskGradeResult) => void;
    onStatus?: (status: ChannelStatus) => void;
  },
  intervalMs = 4000
): (() => void) => {
  let stopped = false;
  let seeded = false;
  let timer: ReturnType<typeof setTimeout> | undefined;
  const seenUploads = new Set<string>();
  const seenGrades = new Map<number, string>();

  const poll = async () => {
    if (typeof document !== 'undefined' && document.hidden) return;
    try {
      const uploads = await getLatestMobileUploads(channelId, 30);
      const contexts = handlers.onGrade ? await getTaskContexts(channelId) : [];
      if (stopped) return;

      // Oldest first, so callers that prepend end with the newest on top.
      for (const upload of [...uploads].reverse()) {
        if (seenUploads.has(upload.file_name)) continue;
        seenUploads.add(upload.file_name);
        if (seeded) handlers.onUpload?.(upload);
      }
      for (const context of contexts) {
        const grade = context.last_grade;
        if (!grade || seenGrades.get(context.problem_number) === grade.graded_at) continue;
        seenGrades.set(context.problem_number, grade.graded_at);
        if (seeded) handlers.onGrade?.(grade);
      }
      seeded = true;
      handlers.onStatus?.('live');
    } catch {
      if (!stopped) handlers.onStatus?.('error');
    }
  };

  const loop = async () => {
    await poll();
    if (!stopped) timer = setTimeout(loop, intervalMs);
  };
  void loop();

  return () => {
    stopped = true;
    if (timer) clearTimeout(timer);
  };
};
