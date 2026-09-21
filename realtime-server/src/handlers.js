'use strict';

const { describeDevice, detectPlatform } = require('./deviceName');

const MAX_IMAGE_BYTES = 8 * 1024 * 1024;
const REQUEST_TTL_MS = 30_000;

const presenceRoom = (userId) => `presence:${userId}`;

const normalizeProblems = (value) => {
  if (!Array.isArray(value)) return null;
  return value
    .filter((item) => item && typeof item === 'object')
    .map((item) => ({ id: Number(item.id), label: String(item.label || '').trim(), type: item.type }))
    .filter((item) => Number.isFinite(item.id) && item.label.length > 0 && item.type === 'open')
    .map((item) => ({ id: item.id, label: item.label, type: 'open' }));
};

const approxBytes = (dataUrl) => {
  const base64 = String(dataUrl).split(',')[1] || '';
  return Math.floor((base64.length * 3) / 4);
};

const registerHandlers = ({ io, registry, now = () => Date.now() }) => {
  const broadcastPresence = (userId) => {
    io.to(presenceRoom(userId)).emit('presence:list', { devices: registry.listDevices(userId) });
  };

  const endLinkAndNotify = (link, reason) => {
    if (!link) return;
    registry.endLink(link.linkId);
    io.to(link.desktopSocketId).emit('link:ended', { reason });
    io.to(link.phoneSocketId).emit('link:ended', { reason });
    broadcastPresence(link.userId);
  };

  io.on('connection', (socket) => {
    const userId = socket.data.authUserId;

    socket.on('presence:subscribe', (payload = {}, callback) => {
      const desktopId = String(payload.desktopId || '').trim();
      if (!desktopId) return callback?.({ ok: false, reason: 'INVALID_PAYLOAD' });

      socket.data.role = 'desktop';
      socket.data.desktopId = desktopId;
      socket.data.desktopName =
        String(payload.name || '').trim() ||
        describeDevice(socket.handshake.headers['user-agent'] || '');
      socket.join(presenceRoom(userId));

      // A desktop that reloaded within the grace window keeps its link.
      const reattached = registry.reattachDesktop({ userId, desktopId, socketId: socket.id });
      if (reattached) {
        socket.emit('link:established', {
          linkId: reattached.linkId,
          peer: registry.getEntry(userId, reattached.phoneDeviceId) ?? { deviceId: reattached.phoneDeviceId },
          examProblems: reattached.examProblems,
        });
      }

      callback?.({ ok: true, devices: registry.listDevices(userId) });
    });

    socket.on('presence:unsubscribe', (_payload, callback) => {
      socket.leave(presenceRoom(userId));
      callback?.({ ok: true });
    });

    socket.on('presence:announce', (payload = {}, callback) => {
      const deviceId = String(payload.deviceId || '').trim();
      if (!deviceId) return callback?.({ ok: false, reason: 'INVALID_PAYLOAD' });

      const userAgent = socket.handshake.headers['user-agent'] || '';
      socket.data.role = 'phone';
      socket.data.deviceId = deviceId;

      registry.announce({
        userId,
        deviceId,
        socketId: socket.id,
        name: String(payload.name || '').trim() || describeDevice(userAgent),
        platform: String(payload.platform || '').trim() || detectPlatform(userAgent),
        userAgent,
        at: now(),
      });

      // A phone whose screen slept keeps its link if it comes back in time.
      const reattached = registry.reattachPhone({ userId, deviceId, socketId: socket.id });
      if (reattached) {
        socket.emit('link:established', {
          linkId: reattached.linkId,
          peer: { desktopId: reattached.desktopId },
          examProblems: reattached.examProblems,
        });
        io.to(reattached.desktopSocketId).emit('link:peer-reconnected', { deviceId });
      }

      broadcastPresence(userId);
      callback?.({ ok: true, deviceId });
    });

    socket.on('presence:withdraw', (_payload, callback) => {
      if (socket.data.deviceId) {
        registry.withdraw({ userId, deviceId: socket.data.deviceId });
        broadcastPresence(userId);
      }
      callback?.({ ok: true });
    });

    socket.on('link:request', (payload = {}, callback) => {
      if (socket.data.role !== 'desktop') return callback?.({ ok: false, reason: 'UNAUTHORIZED' });
      const deviceId = String(payload.deviceId || '').trim();
      if (!deviceId) return callback?.({ ok: false, reason: 'INVALID_PAYLOAD' });

      const created = registry.createRequest({
        userId,
        desktopId: socket.data.desktopId,
        desktopSocketId: socket.id,
        phoneDeviceId: deviceId,
        at: now(),
      });
      if (!created.ok) return callback?.(created);

      io.to(created.request.phoneSocketId).emit('link:incoming', {
        requestId: created.request.requestId,
        desktopName: socket.data.desktopName,
        expiresInMs: REQUEST_TTL_MS,
      });
      broadcastPresence(userId);
      // Remembered so this socket's own request — and only its own — is
      // cancelled if it disconnects before the phone answers.
      socket.data.pendingRequestId = created.request.requestId;
      callback?.({ ok: true, requestId: created.request.requestId });
    });

    socket.on('link:cancel', (payload = {}, callback) => {
      const request = registry.cancelRequest(String(payload.requestId || ''));
      delete socket.data.pendingRequestId;
      if (request) {
        io.to(request.phoneSocketId).emit('link:expired', { requestId: request.requestId });
        broadcastPresence(userId);
      }
      callback?.({ ok: true });
    });

    socket.on('link:respond', (payload = {}, callback) => {
      const requestId = String(payload.requestId || '');
      const resolved = registry.resolveRequest(requestId, Boolean(payload.accept), now());
      if (!resolved.ok) return callback?.(resolved);

      const desktopSocketForRequest = io.sockets.sockets.get(resolved.request.desktopSocketId);
      if (desktopSocketForRequest) delete desktopSocketForRequest.data.pendingRequestId;

      if (!resolved.accepted) {
        io.to(resolved.request.desktopSocketId).emit('link:rejected', {
          deviceId: resolved.request.phoneDeviceId,
        });
        broadcastPresence(userId);
        return callback?.({ ok: true });
      }

      const { link } = resolved;
      // Replay whatever the desktop published before the link existed, so a
      // phone that joins mid-exam gets the problem list without a republish.
      const pendingProblems = desktopSocketForRequest?.data.pendingExamProblems;
      if (Array.isArray(pendingProblems) && pendingProblems.length) {
        registry.setExamProblems(link.linkId, pendingProblems);
      }

      io.to(link.desktopSocketId).emit('link:established', {
        linkId: link.linkId,
        peer: registry.getEntry(userId, link.phoneDeviceId) ?? { deviceId: link.phoneDeviceId },
        examProblems: link.examProblems,
      });
      socket.emit('link:established', {
        linkId: link.linkId,
        peer: { desktopId: link.desktopId },
        examProblems: link.examProblems,
      });
      broadcastPresence(userId);
      callback?.({ ok: true });
    });

    socket.on('link:leave', (_payload, callback) => {
      endLinkAndNotify(registry.getLinkBySocketId(socket.id), 'peer-left');
      callback?.({ ok: true });
    });

    socket.on('link:end', (_payload, callback) => {
      endLinkAndNotify(registry.getLinkBySocketId(socket.id), 'peer-left');
      callback?.({ ok: true });
    });

    socket.on('exam:problems', (payload = {}, callback) => {
      if (socket.data.role !== 'desktop') return callback?.({ ok: false, reason: 'UNAUTHORIZED' });
      const problems = normalizeProblems(payload.problems);
      if (problems === null) return callback?.({ ok: false, reason: 'INVALID_PAYLOAD' });

      // Held on the session so it survives until a link exists.
      socket.data.pendingExamProblems = problems;

      const link = registry.getLinkBySocketId(socket.id);
      if (link) {
        registry.setExamProblems(link.linkId, problems);
        io.to(link.phoneSocketId).emit('exam:problems', { problems });
      }
      callback?.({ ok: true });
    });

    socket.on('answer:submit', (payload = {}, callback) => {
      const link = registry.getLinkBySocketId(socket.id);
      if (!link || link.phoneSocketId !== socket.id) {
        return callback?.({ ok: false, reason: 'NOT_LINKED' });
      }

      const problemId = Number(payload.problemId);
      const image = payload.image;
      if (
        !Number.isFinite(problemId) ||
        typeof image !== 'string' ||
        !image.startsWith('data:image/')
      ) {
        return callback?.({ ok: false, reason: 'INVALID_PAYLOAD' });
      }
      if (approxBytes(image) > MAX_IMAGE_BYTES) {
        return callback?.({ ok: false, reason: 'TOO_LARGE' });
      }

      const entry = registry.getEntry(userId, link.phoneDeviceId);
      io.to(link.desktopSocketId).emit('answer:submit', {
        problemId,
        image,
        deviceId: link.phoneDeviceId,
        deviceName: entry?.name || 'Телефон',
        submittedAt: new Date().toISOString(),
      });
      socket.emit('answer:received', { problemId });
      callback?.({ ok: true });
    });

    socket.on('disconnect', () => {
      const removed = registry.removeSocketPresence(socket.id);
      // The link is *held*, not ended — the grace sweep decides.
      registry.markSocketGone(socket.id, now());

      // Cancel only this socket's own pending request. Sweeping every pending
      // request here would cancel other users' in-flight pairings.
      const ownRequestId = socket.data.pendingRequestId;
      if (ownRequestId) {
        const request = registry.cancelRequest(ownRequestId);
        if (request) {
          io.to(request.desktopSocketId).emit('link:expired', { requestId: ownRequestId });
          io.to(request.phoneSocketId).emit('link:expired', { requestId: ownRequestId });
        }
      }

      if (removed) broadcastPresence(removed.userId);
      else broadcastPresence(userId);
    });
  });

  const sweep = () => {
    const at = now();
    for (const request of registry.sweepRequests(at)) {
      io.to(request.desktopSocketId).emit('link:expired', { requestId: request.requestId });
      io.to(request.phoneSocketId).emit('link:expired', { requestId: request.requestId });
      broadcastPresence(request.userId);
    }
    for (const { link } of registry.sweepGrace(at)) {
      io.to(link.desktopSocketId).emit('link:ended', { reason: 'peer-gone' });
      io.to(link.phoneSocketId).emit('link:ended', { reason: 'peer-gone' });
      broadcastPresence(link.userId);
    }
  };

  return { sweep, broadcastPresence };
};

module.exports = { registerHandlers, MAX_IMAGE_BYTES, REQUEST_TTL_MS, normalizeProblems };
