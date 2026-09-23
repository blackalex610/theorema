import apiClient from "./api";
import type { XpSummary } from "./progress";

export interface NVOQuestion {
  number: number;
  question: string;
  topic: string;
  difficulty: string;
  diagram: boolean;
  diagram_type?: string;
  diagram_config?: Record<string, unknown>;
  open_parts?: string[];
  options: string[] | null;
  correct_answer: string[] | string | null;
  /** Per-sub-part marks, straight off the official keys. Absent on legacy papers. */
  points?: number[];
  /** 'mc' | 'short' | 'open'. Absent on legacy papers. */
  kind?: string;
}

/** Which exam shape a paper was built to. */
export type NVOBlueprintCode = 'nvo2026' | 'classic';

/**
 * The level a paper was generated at. `actual` reproduces the real exam; the
 * other three keep its structure and change only how hard the items are and
 * how long the clock runs. Mirrors `backend/app/nvo_gen/difficulty.py`, which
 * is the authority — this is a copy for the picker, not a second definition.
 */
export type NVODifficultyCode = 'easy' | 'medium' | 'actual' | 'extra_hard';

export interface NVODifficultyInfo {
  code: NVODifficultyCode;
  label: string;
  subtitle: string;
  blurb: string;
  emoji: string;
  xpMultiplier: number;
  timeScale: number;
  /** True for the one level that is the real exam. */
  isActual: boolean;
}

export interface NVOBlueprintInfo {
  code: NVOBlueprintCode;
  label: string;
  subtitle: string;
  years: string;
  questionCount: number;
  mcCount: number;
  shortCount: number;
  openCount: number;
  part1Minutes: number;
  part2Minutes: number;
  totalPoints: number;
}

export interface NVOExam {
  exam_id: string;
  questions: NVOQuestion[];
  /** The level this paper was generated at, as resolved by the server. */
  difficulty?: NVODifficultyCode;
  difficulty_label?: string;
  blueprint?: NVOBlueprintCode;
  blueprint_label?: string;
  /** Where Part 1 ends. 20 on a classic paper, 21 on a 2026 one. */
  part1_count?: number;
  part1_minutes?: number;
  part2_minutes?: number;
  total_points?: number;
  /** Question number the "not to scale" notice prints before. */
  scale_notice_before?: number | null;
  scale_notice?: string;
}

export interface NVOGenerationJobResponse {
  job_id: string;
}

export interface NVOGenerationJobStatus {
  job_id: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  progress: number;
  message: string;
  exam_id: string | null;
}

export interface NVOOpenAnswerImage {
  problemId: number;
  image: string;
}

export interface NVOExamSubmitPayload {
  exam_id: string;
  answers: Record<number, string | Record<string, string>>;
  open_answer_images: NVOOpenAnswerImage[];
  questions?: NVOQuestion[];
}

export interface NVOOpenGradeResult {
  problemId: number;
  score: number;
  max_score: number;
  is_correct: boolean;
  extracted_answer: string;
  feedback: string;
}

export interface NVOExamSubmitResponse {
  exam_id: string;
  open_results: NVOOpenGradeResult[];
  total_open_score: number;
  total_open_max_score: number;
  // The server now grades every question (MCQ included) against its own
  // stored exam and returns the real score here — this is what the results
  // screen and the XP award are based on, not a client-side computation.
  mcq_score: number;
  mcq_max_score: number;
  total_score: number;
  total_max_score: number;
  percentage_correct: number;
  // Every score above is in NVO points (a full paper is out of 100). These
  // split it the way the official result does: Part 1 out of 65, Part 2 out
  // of 35. Absent from servers older than the points change.
  part1_score?: number;
  part1_max_score?: number;
  part2_score?: number;
  part2_max_score?: number;
}

/** One graded sitting as the server records it. */
export interface NVOAttemptSummary {
  exam_id: string;
  difficulty: string;
  format: string;
  mcq_score: number;
  mcq_max_score: number;
  open_score: number;
  open_max_score: number;
  score: number;
  max_score: number;
  percentage_correct: number;
  xp_awarded: boolean;
  created_at: string;
  graded_at: string;
}

/**
 * The signed-in student's own graded attempts, newest first.
 *
 * The exam page has always built its history from localStorage alone, so a
 * student who switched devices or cleared site data lost every past score.
 * The server had the rows all along (/nvo/submit writes one per sitting);
 * this reads them back so history follows the account, not the browser.
 *
 * Summaries only — no questions or answers. Generated exams expire from the
 * server's store after 24h, so per-question review stays a local-device
 * feature and these entries render without a review action.
 */
export async function listNvoAttempts(limit?: number): Promise<NVOAttemptSummary[]> {
  const response = await apiClient.get("/nvo/attempts", {
    params: limit ? { limit } : undefined,
  });
  return Array.isArray(response.data) ? response.data : [];
}

export async function generateNVOExam(): Promise<NVOExam> {
  const response = await apiClient.post("/nvo/generate");
  return response.data;
}

export async function createNVOGenerationJob(
  difficulty?: NVODifficultyCode,
  format?: 'full' | 'short',
  blueprint?: NVOBlueprintCode
): Promise<NVOGenerationJobStatus> {
  const payload: { difficulty?: string; format?: string; blueprint?: string } = {};
  if (difficulty) payload.difficulty = difficulty;
  if (format) payload.format = format;
  if (blueprint) payload.blueprint = blueprint;

  const response = await apiClient.post("/nvo/generate-job",
    Object.keys(payload).length > 0 ? payload : null,
    { timeout: 90000 }
  );
  return response.data;
}

/** The exam shapes the picker offers. Public — no credit is spent to read it. */
export async function getNVOBlueprints(): Promise<NVOBlueprintInfo[]> {
  const response = await apiClient.get('/nvo/blueprints');
  return response.data.blueprints;
}

/** The difficulty levels the picker offers. Public, like the blueprints. */
export async function getNVODifficulties(): Promise<NVODifficultyInfo[]> {
  const response = await apiClient.get('/nvo/difficulties');
  return response.data.difficulties;
}

export async function getNVOGenerationJob(jobId: string): Promise<NVOGenerationJobStatus> {
  const response = await apiClient.get(`/nvo/generate-job/${jobId}`);
  return response.data;
}

export async function getGeneratedNVOExam(examId: string): Promise<NVOExam> {
  const response = await apiClient.get(`/nvo/generated/${examId}`);
  return response.data;
}

export async function getNVOQuestions() {
  const response = await apiClient.get("/nvo/questions");
  return response.data;
}

export async function resetAllXp(confirm: boolean = false): Promise<{ success: boolean; message: string; affected_users: number }> {
  const response = await apiClient.post('/nvo/admin/reset-all-xp', null, { params: { confirm } });
  return response.data;
}

export async function submitNVOExam(payload: NVOExamSubmitPayload): Promise<NVOExamSubmitResponse> {
  const response = await apiClient.post('/nvo/submit', payload);
  return response.data;
}

export interface NVOAwardXpRequest {
  // percentage_correct and difficulty are no longer sent — the server
  // derives both from the NvoAttempt row /nvo/submit wrote for this exam_id,
  // so a client can no longer self-report either. minutes_taken is still
  // client-reported but is clamped server-side to the exam's own duration.
  exam_id: string;
  minutes_taken: number;
}

export interface NVOAwardXpResponse {
  base_xp: number;
  difficulty: string;
  difficulty_multiplier: number;
  difficulty_bonus_xp: number;
  minutes_taken: number;
  time_multiplier: number;
  time_bonus_xp: number;
  final_xp: number;
  percentage_correct: number;
  xp_before: number;
  xp_after: number;
  level_info: XpSummary;
  leveled_up: boolean;
}

export async function awardNvoXp(): Promise<void> {
  // Legacy method - simple 300 XP award
  await apiClient.post('/nvo/award-xp', {});
}

export async function awardNvoXpDetailed(request: NVOAwardXpRequest): Promise<NVOAwardXpResponse> {
  const response = await apiClient.post('/nvo/award-xp', request);
  return response.data;
}

export interface MathAnalysisResult {
  extracted_text: string;
  confidence: 'high' | 'medium' | 'low';
}

export async function analyzeMathImage(imageDataUrl: string): Promise<MathAnalysisResult> {
  const response = await apiClient.post('/mobile/analyze-math', { image_data_url: imageDataUrl }, { timeout: 35000 });
  return response.data;
}
