import ReactMarkdown, { type Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';

import { isBlockCode } from '../utils/markdown';

// Split out of ChatSidebar so the Markdown parser loads with the first
// message rather than with every page (ChatSidebar is in the app shell).
const markdownComponents: Components = {
  p: ({ children }) => <p className="mb-1 last:mb-0">{children}</p>,
  ul: ({ children }) => <ul className="list-disc pl-4 space-y-1">{children}</ul>,
  ol: ({ children }) => <ol className="list-decimal pl-4 space-y-1">{children}</ol>,
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  a: ({ children, href }) => (
    <a href={href} target="_blank" rel="noreferrer" className="underline underline-offset-2">
      {children}
    </a>
  ),
  pre: ({ children }) => <pre className="rounded-lg bg-black/10 p-2.5 overflow-x-auto text-xs">{children}</pre>,
  code({ node: _node, className, children, ...props }) {
    if (isBlockCode(className, children)) {
      return <code className={className} {...props}>{children}</code>;
    }
    return <code className="rounded bg-black/10 px-1 py-0.5 text-[0.92em]" {...props}>{children}</code>;
  },
};

export default function ChatMarkdown({ content }: { content: string }) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
      {content}
    </ReactMarkdown>
  );
}
