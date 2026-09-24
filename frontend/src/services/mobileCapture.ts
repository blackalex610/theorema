import { fileToJpegFile } from '../utils/imageCapture';
import apiClient, { API_BASE_URL } from './api';

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

export const subscribeToMobileUploads = (
  channelId: string,
  onUpload: (event: UploadEvent) => void,
  onError?: () => void,
  onGrade?: (event: TaskGradeResult) => void
): EventSource => {
  const source = new EventSource(`${API_BASE_URL}/mobile/uploads/stream?channel_id=${encodeURIComponent(channelId)}`);

  source.addEventListener('upload', (event) => {
    try {
      const parsed = JSON.parse((event as MessageEvent).data) as UploadEvent;
      onUpload(parsed);
    } catch {
      // Ignore malformed events and keep stream alive.
    }
  });

  source.onerror = () => {
    if (onError) onError();
  };

  source.addEventListener('grade', (event) => {
    if (!onGrade) return;
    try {
      const parsed = JSON.parse((event as MessageEvent).data) as TaskGradeResult;
      onGrade(parsed);
    } catch {
      // Ignore malformed events and keep stream alive.
    }
  });

  return source;
};
