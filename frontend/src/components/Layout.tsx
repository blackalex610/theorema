import React, { useMemo, useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import ChatSidebar from './ChatSidebar';
import BugReportButton from './BugReportButton';

const ASK_ASSISTANT_EVENT = 'ask-assistant-from-selection';

/** Routes that bring their own chrome: auth, marketing, and the legal pages. */
const UNCHROMED = new Set(['/', '/about', '/privacy', '/terms']);

/**
 * Application shell.
 *
 * There is deliberately no inner scroll container here. The document is the
 * only scroller, which is what lets Lenis and Motion's viewport hooks work on
 * every screen, and what restores the browser's own scroll restoration.
 */
const Layout: React.FC = () => {
  const [isChatOpen, setIsChatOpen] = useState(false);
  const location = useLocation();

  const isUnchromed = useMemo(() => UNCHROMED.has(location.pathname), [location.pathname]);

  React.useEffect(() => {
    const openChatFromSelection = () => setIsChatOpen(true);
    window.addEventListener(ASK_ASSISTANT_EVENT, openChatFromSelection as EventListener);
    return () => window.removeEventListener(ASK_ASSISTANT_EVENT, openChatFromSelection as EventListener);
  }, []);

  if (isUnchromed) {
    return <Outlet />;
  }

  return (
    <div className="min-h-dvh bg-paper">
      <Outlet />

      <ChatSidebar
        isOpen={isChatOpen}
        onOpen={() => setIsChatOpen(true)}
        onClose={() => setIsChatOpen(false)}
      />
      <BugReportButton />
    </div>
  );
};

export default Layout;
