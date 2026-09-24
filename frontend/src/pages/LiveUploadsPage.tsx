import React, { useEffect, useMemo, useState } from 'react';
import { generateChannelId, isStrongChannelId } from '../utils/channelId';
import { getLatestMobileUploads, subscribeToMobileUploads, type UploadEvent } from '../services/mobileCapture';
import { SkeletonCard, Bone } from '../components/Skeleton';

const CHANNEL_STORAGE_KEY = 'mobile_upload_channel_v1';


const formatTime = (iso: string): string => {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleString();
};

const LiveUploadsPage: React.FC = () => {
  const [channelId, setChannelId] = useState('');
  const [uploads, setUploads] = useState<UploadEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState<'connecting' | 'live' | 'error'>('connecting');

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const channelFromQuery = (params.get('channel') || '').trim();

    let nextChannel = channelFromQuery;
    if (!nextChannel) {
      const stored = (localStorage.getItem(CHANNEL_STORAGE_KEY) || '').trim();
      // Ids from before the CSPRNG change were guessable; replace them.
      nextChannel = isStrongChannelId(stored) ? stored : generateChannelId();
    }

    localStorage.setItem(CHANNEL_STORAGE_KEY, nextChannel);
    setChannelId(nextChannel);

    const url = new URL(window.location.href);
    url.searchParams.set('channel', nextChannel);
    window.history.replaceState(null, '', url.toString());
  }, []);

  useEffect(() => {
    if (!channelId) return;

    let mounted = true;

    const init = async () => {
      try {
        const initial = await getLatestMobileUploads(channelId, 24);
        if (!mounted) return;
        setUploads(initial);
      } finally {
        if (mounted) setLoading(false);
      }
    };

    void init();

    const source = subscribeToMobileUploads(
      channelId,
      (event) => {
        setStatus('live');
        setUploads((prev) => {
          if (prev.some((u) => u.file_name === event.file_name)) return prev;
          return [event, ...prev].slice(0, 50);
        });
      },
      () => {
        setStatus('error');
      }
    );

    source.onopen = () => setStatus('live');

    return () => {
      mounted = false;
      source.close();
    };
  }, [channelId]);

  const mobilePairUrl = useMemo(() => {
    if (!channelId) return '';
    const url = new URL(window.location.origin + '/mobile-capture');
    url.searchParams.set('channel', channelId);
    return url.toString();
  }, [channelId]);

  const qrImageUrl = useMemo(() => {
    if (!mobilePairUrl) return '';
    return `https://api.qrserver.com/v1/create-qr-code/?size=220x220&data=${encodeURIComponent(mobilePairUrl)}`;
  }, [mobilePairUrl]);

  const statusText = useMemo(() => {
    if (status === 'live') return 'Live connection active';
    if (status === 'error') return 'Connection issue. Retrying automatically...';
    return 'Connecting...';
  }, [status]);

  return (
    <div className="min-h-screen bg-slate-100 p-4 sm:p-6">
      <div className="mx-auto max-w-5xl rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden">
        <div className="border-b border-slate-100 px-5 py-4 flex flex-wrap items-center justify-between gap-2">
          <div>
            <h1 className="text-lg font-bold text-slate-900">Desktop Live Uploads</h1>
            <p className="mt-1 text-sm text-slate-600">
              Photos uploaded from your phone appear here automatically.
            </p>
          </div>
          <span
            className={`px-3 py-1 rounded-full text-xs font-semibold ${
              status === 'live'
                ? 'bg-emerald-100 text-emerald-700'
                : status === 'error'
                ? 'bg-red-100 text-red-700'
                : 'bg-amber-100 text-amber-700'
            }`}
          >
            {statusText}
          </span>
        </div>

        <div className="p-5">
          <div className="mb-5 rounded-xl border border-slate-200 bg-slate-50 p-4">
            <h2 className="text-sm font-semibold text-slate-800">Phone Pairing</h2>
            <p className="mt-1 text-xs text-slate-600">Scan QR on your phone, open the link, and upload. Only this channel is shown here.</p>
            <p className="mt-2 text-xs text-slate-500">Channel: <span className="font-mono">{channelId || '...'}</span></p>
            {qrImageUrl && (
              <div className="mt-3 flex flex-wrap items-center gap-4">
                <img src={qrImageUrl} alt="Pairing QR" className="h-36 w-36 rounded-lg border border-slate-200 bg-white p-2" />
                <div className="min-w-0 flex-1">
                  <p className="text-xs text-slate-600 mb-1">Pair link</p>
                  <a href={mobilePairUrl} target="_blank" rel="noreferrer" className="block break-all text-xs text-blue-700 underline">{mobilePairUrl}</a>
                </div>
              </div>
            )}
          </div>

          {loading ? (
            <div className="space-y-3">
              {Array.from({ length: 3 }).map((_, i) => (
                <SkeletonCard key={i}>
                  <Bone className="h-3 w-32 mb-2" />
                  <Bone className="h-2 w-full" />
                </SkeletonCard>
              ))}
            </div>
          ) : uploads.length === 0 ? (
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
              No uploads yet. Open /mobile-capture on your phone and upload a photo.
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {uploads.map((item) => (
                <article key={item.file_name} className="rounded-xl border border-slate-200 bg-white p-2">
                  <a href={item.file_url} target="_blank" rel="noreferrer" className="block">
                    <img
                      src={item.file_url}
                      alt={item.file_name}
                      className="w-full aspect-[4/3] object-cover rounded-lg bg-slate-100"
                      loading="lazy"
                    />
                  </a>
                  <div className="pt-2 px-1">
                    <p className="text-xs text-slate-500 truncate" title={item.file_name}>{item.file_name}</p>
                    <p className="text-xs text-slate-500">{(item.size_bytes / 1024).toFixed(1)} KB</p>
                    <p className="text-xs text-slate-500">{formatTime(item.uploaded_at)}</p>
                  </div>
                </article>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default LiveUploadsPage;
