import React, { useMemo, useRef, useState } from 'react';
import {
  getTaskContexts,
  setTaskContext,
  submitTaskGradeFromPhoto,
  uploadMobilePhoto,
  type TaskContext,
  type TaskGradeResult,
} from '../services/mobileCapture';
import { renderMathText } from '../components/MathRenderer';

const MobileCapturePage: React.FC = () => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [uploadedUrl, setUploadedUrl] = useState('');
  const [uploadedUrlByProblem, setUploadedUrlByProblem] = useState<Record<number, string>>({});
  const [availableTasks, setAvailableTasks] = useState<TaskContext[]>([]);
  const [gradeByProblem, setGradeByProblem] = useState<Record<number, TaskGradeResult>>({});
  const [activeProblemNumber, setActiveProblemNumber] = useState<number | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const channelId = useMemo(() => {
    const params = new URLSearchParams(window.location.search);
    return (params.get('channel') || '').trim();
  }, []);

  React.useEffect(() => {
    if (!channelId) return;

    let mounted = true;
    const loadContexts = async () => {
      try {
        const contexts = await getTaskContexts(channelId);
        if (!mounted) return;
        setAvailableTasks(contexts);
      } catch {
        if (!mounted) return;
        setAvailableTasks([]);
      }
    };

    void loadContexts();
    const intervalId = window.setInterval(() => {
      void loadContexts();
    }, 2000);

    return () => {
      mounted = false;
      window.clearInterval(intervalId);
    };
  }, [channelId]);

  // When opened via QR channel, always keep task-upload mode enabled so uploads include problem_number.
  const isTaskLanding = Boolean(channelId);

  const handleChooseTaskUpload = (problemNumber: number) => {
    setActiveProblemNumber(problemNumber);
    setUploadError('');
    fileInputRef.current?.click();
  };

  const handleTaskUpload = async (file: File, problemNumber: number) => {
    if (!channelId) return;

    const context = availableTasks.find((item) => item.problem_number === problemNumber);
    if (!context) {
      setUploadError('Задачата не е налична за този линк.');
      return;
    }

    setIsUploading(true);
    setUploadError('');
    setUploadedUrl('');

    try {
      await setTaskContext({
        channel_id: channelId,
        problem_number: context.problem_number,
        a: context.a,
        b: context.b,
        correct_xy: context.correct_xy,
      });

      const uploaded = await uploadMobilePhoto(file, channelId, problemNumber);
      setUploadedUrl(uploaded.file_url);
      setUploadedUrlByProblem((current) => ({
        ...current,
        [problemNumber]: uploaded.file_url,
      }));

      const grade = await submitTaskGradeFromPhoto({
        channel_id: channelId,
        file_name: uploaded.file_name,
        problem_number: problemNumber,
      });

      setGradeByProblem((current) => ({
        ...current,
        [problemNumber]: grade,
      }));
    } catch {
      setUploadError('Автоматичната проверка от снимка не успя. Опитай отново.');
    } finally {
      setIsUploading(false);
      setActiveProblemNumber(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null;
    setSelectedFile(file);
    setUploadError('');
    setUploadedUrl('');

    if (file && channelId && activeProblemNumber !== null && isTaskLanding) {
      void handleTaskUpload(file, activeProblemNumber);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile || !channelId) return;

    setIsUploading(true);
    setUploadError('');
    setUploadedUrl('');

    try {
      const result = await uploadMobilePhoto(selectedFile, channelId);
      setUploadedUrl(result.file_url);
    } catch {
      setUploadError('Upload failed. Check backend server and try again.');
    } finally {
      setIsUploading(false);
    }
  };

  const previewUrl = useMemo(() => {
    if (!selectedFile || isTaskLanding) return '';
    return URL.createObjectURL(selectedFile);
  }, [selectedFile, isTaskLanding]);

  return (
    <div className="min-h-screen bg-slate-100 p-4 sm:p-6">
      <div className="mx-auto max-w-xl rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden">
        <div className="border-b border-slate-100 px-5 py-4">
          <h1 className="text-lg font-bold text-slate-900">
            {isTaskLanding ? 'Upload' : 'Phone Capture'}
          </h1>
          {!isTaskLanding && (
            <p className="mt-1 text-sm text-slate-600">
              Open this page from the desktop pairing link, then capture and upload to that desktop session.
            </p>
          )}
          {channelId ? (
            <p className="mt-1 text-xs text-slate-500">
              Connected channel: <span className="font-mono">{channelId}</span>
            </p>
          ) : (
            <p className="mt-1 text-xs text-red-600 font-semibold">
              Missing channel. Open this page by scanning the QR from desktop live uploads.
            </p>
          )}
        </div>

        <div className="p-5 space-y-4">
          {/* Plain-language disclosure at the point of capture. The photo
              leaves the device and goes to a third-party AI service; saying
              so here is the difference between consent and surprise. */}
          <p className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-[11px] leading-relaxed text-slate-600">
            Снимката се изпраща за автоматична проверка към OpenAI и се съхранява до{' '}
            <strong>24 часа</strong>, след което се изтрива. Снимай само решението си —
            не и лица или лични документи.{' '}
            <a href="/privacy" target="_blank" rel="noreferrer" className="underline">
              Повече
            </a>
          </p>

          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            capture="environment"
            onChange={handleFileChange}
            className="hidden"
          />

          {isTaskLanding ? (
            <div className="space-y-3">
              {availableTasks.map((task) => {
                const grade = gradeByProblem[task.problem_number];
                const uploadedTaskUrl = uploadedUrlByProblem[task.problem_number];
                const isBusy = isUploading && activeProblemNumber === task.problem_number;

                return (
                  <div key={task.problem_number} className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-1">Задача {task.problem_number}</p>
                        {task.statement
                          ? <div className="text-sm font-medium text-slate-900 leading-snug">{renderMathText(task.statement)}</div>
                          : <p className="text-sm font-semibold text-slate-900">Problem {task.problem_number}</p>
                        }
                      </div>
                      <button
                        type="button"
                        onClick={() => handleChooseTaskUpload(task.problem_number)}
                        disabled={!channelId || isUploading}
                        className="shrink-0 rounded-xl bg-violet-600 px-4 py-2 text-sm font-semibold text-white hover:bg-violet-700 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {isBusy ? 'Uploading...' : 'Upload'}
                      </button>
                    </div>

                    {uploadedTaskUrl && (
                      <div className="mt-3 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700">
                        <p className="font-semibold">Uploaded successfully.</p>
                        <a href={uploadedTaskUrl} target="_blank" rel="noreferrer" className="break-all underline">
                          {uploadedTaskUrl}
                        </a>
                      </div>
                    )}

                    {grade && (
                      <div className={`mt-3 rounded-lg border p-3 text-sm ${grade.is_correct ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-red-200 bg-red-50 text-red-800'}`}>
                        <p className="font-semibold">{grade.is_correct ? '✅ Верен' : '❌ Грешен'} • {grade.score}/100</p>
                        <div className="mt-1">{renderMathText(grade.feedback)}</div>
                      </div>
                    )}
                  </div>
                );
              })}

              {!availableTasks.length && (
                <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
                  Чакаме задачите от desktop... Остави страницата отворена за 2-3 секунди и ще се появят автоматично.
                </div>
              )}
            </div>
          ) : (
            <>
              <label className="block text-sm font-semibold text-slate-700">
                Capture or choose image
              </label>

              <input
                type="file"
                accept="image/*"
                capture="environment"
                onChange={(event) => {
                  const file = event.target.files?.[0] ?? null;
                  setSelectedFile(file);
                  setUploadError('');
                  setUploadedUrl('');
                }}
                className="block w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700 file:mr-3 file:rounded-md file:border-0 file:bg-blue-600 file:px-3 file:py-1.5 file:text-sm file:font-semibold file:text-white hover:file:bg-blue-700"
              />

              <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
                {selectedFile ? (
                  <>
                    <p><span className="font-semibold">File:</span> {selectedFile.name}</p>
                    <p><span className="font-semibold">Size:</span> {(selectedFile.size / 1024).toFixed(1)} KB</p>
                    <p><span className="font-semibold">Type:</span> {selectedFile.type || 'Unknown'}</p>
                    <p className="mt-2 text-emerald-700 font-semibold">Capture success. Ready to upload to PC.</p>
                  </>
                ) : (
                  <p>No photo selected yet.</p>
                )}
              </div>

              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={handleUpload}
                  disabled={!selectedFile || isUploading || !channelId}
                  className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {isUploading ? 'Uploading...' : 'Upload To PC'}
                </button>
              </div>
            </>
          )}

          {uploadError && (
            <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
              {uploadError}
            </div>
          )}

          {uploadedUrl && !isTaskLanding && (
            <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700">
              <p className="font-semibold">Uploaded successfully.</p>
              <a href={uploadedUrl} target="_blank" rel="noreferrer" className="break-all underline">
                {uploadedUrl}
              </a>
            </div>
          )}

          {!isTaskLanding && previewUrl && (
            <div className="rounded-xl border border-slate-200 p-2 bg-white">
              <img
                src={previewUrl}
                alt="Captured preview"
                className="w-full max-h-[60vh] object-contain rounded-lg"
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default MobileCapturePage;
