import apiClient from './api';
import { logError } from '../utils/errorLogger';

export type ChatRole = 'user' | 'assistant';

export interface ChatMessage {
  role: ChatRole;
  content: string;
}

interface ChatResponse {
  reply: string;
}

export type DiagramType = 'triangle' | 'parallel_lines' | 'coordinate_plane' | 'rectangle' | 'cube';

export interface DiagramData {
  type: DiagramType;
  // Shape varies by `type`; DiagramRenderer normalises each field it reads.
  elements: Record<string, unknown>;
}

interface DiagramResponse {
  diagram: DiagramData;
}

export const sendChatMessage = async (
  messages: ChatMessage[],
  lessonTitle?: string
): Promise<string> => {
  try {
    const response = await apiClient.post<ChatResponse>('/ai/chat', {
      messages,
      lesson_title: lessonTitle,
    });
    return response.data.reply;
  } catch (error) {
    logError(error, {
      source: 'ai-chat',
      level: 'warning',
      messageCount: messages.length,
      lessonTitle,
    });
    throw error;
  }
};

export const generateDiagram = async (problem: string): Promise<DiagramData> => {
  try {
    const response = await apiClient.post<DiagramResponse>('/ai/diagram', { problem });
    return response.data.diagram;
  } catch (error) {
    logError(error, {
      source: 'ai-diagram',
      level: 'warning',
      problemLength: problem?.length || 0,
    });
    throw error;
  }
};
