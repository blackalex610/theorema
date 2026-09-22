import apiClient from './api';
import type { StrandRow, TopicRow } from './classrooms';

/**
 * Schools — the level a director buys at.
 *
 * Note what is absent from these types: there is no student row anywhere. A
 * director sees classes, counts, bands and topic percentages. The child who
 * typed a class code consented to one teacher seeing their work, not to the
 * whole building, and the API is built so the question cannot even be asked.
 */

export interface School {
  id: number;
  name: string;
  city: string | null;
  join_code: string;
  is_active: boolean;
  created_at: string;
}

/** A school as a teacher who joined it sees it — no join code. */
export interface JoinedSchool {
  id: number;
  name: string;
  city: string | null;
  is_active: boolean;
}

export interface SchoolClassRow {
  classroom_id: number;
  name: string;
  grade_level: number | null;
  teacher_name: string;
  /** A count. Never a list of who is in it. */
  students: number;
  students_with_data: number;
  average_latest_score: number | null;
}

export interface GradeRow {
  grade_level: number | null;
  classes: number;
  students: number;
}

/** Latest score per student, bucketed. Latest, not average — see the API. */
export interface ReadinessBand {
  key: 'excellent' | 'good' | 'borderline' | 'at_risk';
  label: string;
  students: number;
}

export interface SchoolOverview extends School {
  class_count: number;
  teacher_count: number;
  /** Distinct children across attached classes — what a licence counts. */
  seats_used: number;
  students_with_data: number;
  classes: SchoolClassRow[];
  grades: GradeRow[];
  readiness: ReadinessBand[];
  /** Below this many questions asked, a topic is shown greyed, never ranked. */
  min_asked_for_ranking: number;
  topics: TopicRow[];
  strands: StrandRow[];
  weakest: TopicRow[];
}

export async function createSchool(name: string, city?: string | null): Promise<School> {
  const { data } = await apiClient.post<School>('/schools', { name, city: city ?? null });
  return data;
}

export async function listSchoolsIDirect(): Promise<School[]> {
  const { data } = await apiClient.get<{ schools: School[] }>('/schools');
  return data.schools;
}

export async function listSchoolsIJoined(): Promise<JoinedSchool[]> {
  const { data } = await apiClient.get<{ schools: JoinedSchool[] }>('/schools/mine');
  return data.schools;
}

export async function joinSchool(joinCode: string): Promise<JoinedSchool> {
  const { data } = await apiClient.post<JoinedSchool>('/schools/join', {
    join_code: joinCode,
  });
  return data;
}

export async function getSchoolOverview(schoolId: number): Promise<SchoolOverview> {
  const { data } = await apiClient.get<SchoolOverview>(`/schools/${schoolId}`);
  return data;
}

/** The teacher attaches their own class. A director cannot do this for them. */
export async function attachClassroom(
  schoolId: number,
  classroomId: number
): Promise<{ classroom_id: number; school_id: number | null }> {
  const { data } = await apiClient.post(`/schools/${schoolId}/classrooms`, {
    classroom_id: classroomId,
  });
  return data;
}

export async function detachClassroom(
  classroomId: number
): Promise<{ classroom_id: number; school_id: number | null }> {
  const { data } = await apiClient.delete(`/schools/classrooms/${classroomId}`);
  return data;
}
