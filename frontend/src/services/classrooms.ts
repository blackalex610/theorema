import apiClient from './api';

/**
 * Classrooms — the teacher's side of the product, and the student's consent
 * to be part of it.
 *
 * There is no teacher role: you teach the classes you created (`listMyClasses`)
 * and attend the ones you joined (`listClassesIJoined`).
 */

export interface Classroom {
  id: number;
  name: string;
  join_code: string;
  grade_level: number | null;
  is_active: boolean;
  created_at: string;
  student_count: number;
}

/** A class as a student sees it — no join code, no roster. */
export interface JoinedClassroom {
  id: number;
  name: string;
  grade_level: number | null;
  is_active: boolean;
}

export interface RosterRow {
  student_id: number;
  name: string;
  is_guest: boolean;
  joined_at: string;
  total_xp: number;
  level: number;
  streak_days: number;
  exams_taken: number;
  /** null when the student has not finished an exam yet. */
  average_exam_score: number | null;
  best_exam_score: number | null;
  last_exam_at: string | null;
}

export interface ClassroomDetail extends Classroom {
  roster: RosterRow[];
}

export async function createClassroom(
  name: string,
  gradeLevel?: number | null
): Promise<Classroom> {
  const { data } = await apiClient.post<Classroom>('/classrooms', {
    name,
    grade_level: gradeLevel ?? null,
  });
  return data;
}

export async function listMyClasses(): Promise<Classroom[]> {
  const { data } = await apiClient.get<{ classrooms: Classroom[] }>('/classrooms');
  return data.classrooms;
}

export async function listClassesIJoined(): Promise<JoinedClassroom[]> {
  const { data } = await apiClient.get<{ classrooms: JoinedClassroom[] }>('/classrooms/mine');
  return data.classrooms;
}

export async function getClassroom(id: number): Promise<ClassroomDetail> {
  const { data } = await apiClient.get<ClassroomDetail>(`/classrooms/${id}`);
  return data;
}

export async function joinClassroom(joinCode: string): Promise<JoinedClassroom> {
  const { data } = await apiClient.post<JoinedClassroom>('/classrooms/join', {
    join_code: joinCode,
  });
  return data;
}

export async function archiveClassroom(id: number): Promise<Classroom> {
  const { data } = await apiClient.post<Classroom>(`/classrooms/${id}/archive`);
  return data;
}

export async function removeStudent(classroomId: number, studentId: number): Promise<void> {
  await apiClient.delete(`/classrooms/${classroomId}/members/${studentId}`);
}

export async function leaveClassroom(classroomId: number): Promise<void> {
  await apiClient.delete(`/classrooms/${classroomId}/leave`);
}
