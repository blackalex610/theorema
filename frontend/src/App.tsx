import { Suspense, lazy } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import SmoothScroll from './components/SmoothScroll';
import RouteFallback from './components/RouteFallback';
import LandingPage from './pages/LandingPage';
import AuthPage from './pages/AuthPage';

// Everything past the marketing and auth screens is split out of the initial
// bundle. The heavy ones are the reason: PlaygroundPage alone is ~4.7k lines of
// diagram generators, and TheoryPage/NVOPracticeExamPage pull in KaTeX and
// markdown rendering. None of it is needed to render / or /login.
const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const ProgressSummaryPage = lazy(() => import('./pages/ProgressSummaryPage'));
const GradesPage = lazy(() => import('./pages/GradesPage'));
const TopicsPage = lazy(() => import('./pages/TopicsPage'));
const LessonsPage = lazy(() => import('./pages/LessonsPage'));
const ExercisesPage = lazy(() => import('./pages/ExercisesPage'));
const LearnGradesPage = lazy(() => import('./pages/LearnGradesPage'));
const LearnTopicsPage = lazy(() => import('./pages/LearnTopicsPage'));
const LearnLessonsPage = lazy(() => import('./pages/LearnLessonsPage'));
const TheoryPage = lazy(() => import('./pages/TheoryPage'));
const NVOPracticeExamPage = lazy(() => import('./pages/NVOPracticeExamPage'));
const PlaygroundPage = lazy(() => import('./pages/PlaygroundPage'));
const MobileCapturePage = lazy(() => import('./pages/MobileCapturePage'));
const LiveUploadsPage = lazy(() => import('./pages/LiveUploadsPage'));
const ControllerPage = lazy(() => import('./pages/ControllerPage'));
// Teacher side of the product: create a class, hand out the code, watch the
// roster. Same account can also be a student in someone else's class.
const ClassroomsPage = lazy(() => import('./pages/ClassroomsPage'));
const ClassroomDetailPage = lazy(() => import('./pages/ClassroomDetailPage'));
// Public legal documents: reachable signed-out, and linked from the footer
// and the sign-in screen, because a privacy policy nobody can open is not one.
const PrivacyPage = lazy(() => import('./pages/PrivacyPage'));
const TermsPage = lazy(() => import('./pages/TermsPage'));
import SettingsModal from './components/SettingsModal';
import { AuthProvider } from './context/AuthContext';
import { ConnectProvider } from './context/ConnectContext';
import { SettingsProvider } from './context/SettingsContext';
import { XpProvider } from './context/XpContext';
import { DeveloperModeProvider, useIsDevMode } from './context/DeveloperModeContext';
import RequireAuth from './components/RequireAuth';
import { TooltipProvider } from '@/components/ui/tooltip';

// Inner component to access dev mode for conditional routes
function AppRoutes() {
  const isDevMode = useIsDevMode();

  return (
    <Router>
      <SmoothScroll>
        <SettingsModal />
        <Suspense fallback={<RouteFallback />}>
          <Routes>
            <Route path="/" element={<Layout />}>
              {/* Public */}
              <Route index element={<AuthPage />} />
              <Route path="about" element={<LandingPage />} />
              {/* /login and /register predate the two-button auth page — kept
                  as redirects so old links and bookmarks still land somewhere. */}
              <Route path="login" element={<Navigate to="/" replace />} />
              <Route path="register" element={<Navigate to="/" replace />} />
              <Route path="privacy" element={<PrivacyPage />} />
              <Route path="terms" element={<TermsPage />} />
              {/* Phone-pairing pages are opened by QR code from a device that has
                  no session of its own — they are scoped by channel id, not login. */}
              <Route path="mobile-capture" element={<MobileCapturePage />} />

              {/* Everything below requires a signed-in user. */}
              <Route element={<RequireAuth />}>
                <Route path="dashboard" element={<DashboardPage />} />
                <Route path="progress" element={<ProgressSummaryPage />} />
                <Route path="classrooms" element={<ClassroomsPage />} />
                <Route path="classrooms/:classroomId" element={<ClassroomDetailPage />} />
                <Route path="grades" element={<GradesPage />} />
                <Route path="grades/:gradeId/topics" element={<TopicsPage />} />
                <Route path="topics/:topicId/lessons" element={<LessonsPage />} />
                <Route path="lessons/:lessonId/exercises" element={<ExercisesPage />} />
                <Route path="learn/grades" element={<LearnGradesPage />} />
                <Route path="learn/grades/:gradeId/topics" element={<LearnTopicsPage />} />
                <Route path="learn/topics/:topicId/lessons" element={<LearnLessonsPage />} />
                <Route path="learn/lessons/:lessonId/theory" element={<TheoryPage />} />
                <Route path="nvo/practice" element={<NVOPracticeExamPage />} />
                <Route path="live-uploads" element={<LiveUploadsPage />} />
                {/* Developer-only routes */}
                {isDevMode && <Route path="playground" element={<PlaygroundPage />} />}
              </Route>

              {/* Unknown paths previously rendered Layout with an empty
                  Outlet — a blank page with no error and no redirect. */}
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
            <Route path="controller" element={<ControllerPage />} />
            {/* Preferred path; /controller stays for existing bookmarks. */}
            <Route path="connect" element={<ControllerPage />} />
            {/* Redirect playground to dashboard if not in dev mode */}
            {!isDevMode && <Route path="playground" element={<Navigate to="/dashboard" replace />} />}
          </Routes>
        </Suspense>
      </SmoothScroll>
    </Router>
  );
}

function App() {
  return (
    <AuthProvider>
      <DeveloperModeProvider>
        <ConnectProvider>
          <SettingsProvider>
            <XpProvider>
              <TooltipProvider delayDuration={200}>
                <AppRoutes />
              </TooltipProvider>
            </XpProvider>
          </SettingsProvider>
        </ConnectProvider>
      </DeveloperModeProvider>
    </AuthProvider>
  );
}

export default App;
