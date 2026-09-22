import apiClient from './api';
import type { TopicRow } from './classrooms';
import type { NVOExam } from './nvo';

/**
 * Assignments — one generated paper, sat by a whole class.
 *
 * The teacher's own daily exam credit pays for generating the paper; the
 * students who sit it are not charged, which is why `openAssignment` is a
 * separate call from the ordinary exam-generation flow.
 */

export interface Assignment {
  id: number;
  classroom_id: number;
  title: string;
  exam_id: string;
  difficulty: string | null;
  format: string | null;
  blueprint: string | null;
  due_at: string | null;
  is_open: boolean;
  created_at: string;
  student_count: number;
  submitted_count: number;
}

/** An assignment as the student sees it — no exam id, no class statistics. */
export interface StudentAssignment {
  id: number;
  title: string;
  class_name: string;
  classroom_id: number;
  due_at: string | null;
  is_open: boolean;
  submitted: boolean;
  created_at: string;
}

export interface AssignmentStudentRow {
  student_id: number;
  name: string;
  submitted: boolean;
  percentage_correct: number | null;
  submitted_at: string | null;
}

/**
 * One question, across everyone who sat the paper. Only meaningful because
 * the whole class answered the same question N.
 */
export interface AssignmentQuestionRow {
  question_number: number;
  topic_key: string;
  topic_label: string;
  answered: number;
  wrong: number;
  percent_correct: number;
}

export interface AssignmentReport extends Assignment {
  rows: AssignmentStudentRow[];
  questions: AssignmentQuestionRow[];
}

export interface CreateAssignmentInput {
  classroomId: number;
  title: string;
  dueAt?: string | null;
  difficulty?: string | null;
  format?: string | null;
  blueprint?: string | null;
}

export async function createAssignment(
  input: CreateAssignmentInput
): Promise<AssignmentReport> {
  const { data } = await apiClient.post<AssignmentReport>('/assignments', {
    classroom_id: input.classroomId,
    title: input.title,
    due_at: input.dueAt ?? null,
    difficulty: input.difficulty ?? null,
    format: input.format ?? null,
    blueprint: input.blueprint ?? null,
  });
  return data;
}

export async function listClassAssignments(classroomId: number): Promise<Assignment[]> {
  const { data } = await apiClient.get<{ assignments: Assignment[] }>(
    `/assignments/class/${classroomId}`
  );
  return data.assignments;
}

export async function listMyAssignments(): Promise<StudentAssignment[]> {
  const { data } = await apiClient.get<{ assignments: StudentAssignment[] }>(
    '/assignments/mine'
  );
  return data.assignments;
}

export async function getAssignmentReport(assignmentId: number): Promise<AssignmentReport> {
  const { data } = await apiClient.get<AssignmentReport>(`/assignments/${assignmentId}`);
  return data;
}

export async function closeAssignment(assignmentId: number): Promise<AssignmentReport> {
  const { data } = await apiClient.post<AssignmentReport>(`/assignments/${assignmentId}/close`);
  return data;
}

export async function reopenAssignment(assignmentId: number): Promise<AssignmentReport> {
  const { data } = await apiClient.post<AssignmentReport>(`/assignments/${assignmentId}/reopen`);
  return data;
}

/**
 * Fetch the pinned paper for a student to sit.
 *
 * Deliberately not part of the normal generate flow: no generation runs and
 * the student's daily exam quota is untouched.
 */
export async function openAssignment(assignmentId: number): Promise<NVOExam> {
  const { data } = await apiClient.post<NVOExam>(`/assignments/${assignmentId}/open`);
  return data;
}

export type { TopicRow };
