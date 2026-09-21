'use strict';

const crypto = require('crypto');

const DEFAULT_REQUEST_TTL_MS = 30_000;
const DEFAULT_GRACE_MS = 30_000;

/**
 * Presence + link state for the phone-connect feature.
 *
 * Deliberately owns no timers and no sockets: expiry is expressed as an
 * `expiresAt`/`graceUntil` stamp and driven by `sweepRequests`/`sweepGrace`,
 * which the caller runs on an interval. That keeps every expiry path testable
 * with a plain number instead of fake timers.
 *
 * `busy` is *derived*, never stored, so it cannot drift out of sync with the
 * link and pending-request indexes the way a cached flag would.
 */
const createRegistry = ({
  requestTtlMs = DEFAULT_REQUEST_TTL_MS,
  graceMs = DEFAULT_GRACE_MS,
  newId = () => crypto.randomUUID(),
} = {}) => {
  const presenceByUser = new Map();        // userId -> Map<deviceId, entry>
  const presenceBySocket = new Map();      // socketId -> { userId, deviceId }
  const links = new Map();                 // linkId -> link
  const linkByDesktopId = new Map();       // desktopId -> linkId
  const linkByPhoneDeviceId = new Map();   // deviceId -> linkId
  const linkBySocketId = new Map();        // socketId -> linkId
  const pendingRequests = new Map();       // requestId -> request
  const pendingByDevice = new Map();       // deviceId -> requestId
  const pendingByDesktopId = new Map();    // desktopId -> requestId

  const devicesFor = (userId) => {
    let map = presenceByUser.get(userId);
    if (!map) {
      map = new Map();
      presenceByUser.set(userId, map);
    }
    return map;
  };

  const isBusy = (deviceId) =>
    linkByPhoneDeviceId.has(deviceId) || pendingByDevice.has(deviceId);

  const publicDevice = (entry) => ({
    deviceId: entry.deviceId,
    name: entry.name,
    platform: entry.platform,
    announcedAt: entry.announcedAt,
    busy: isBusy(entry.deviceId),
  });

  const announce = ({ userId, deviceId, socketId, name, platform, userAgent, at }) => {
    const map = devicesFor(userId);
    const existing = map.get(deviceId);

    if (existing && existing.socketId !== socketId) {
      presenceBySocket.delete(existing.socketId);
    }

    const entry = {
      deviceId,
      socketId,
      name,
      platform,
      userAgent,
      // Preserved across reconnects so the desktop list does not flicker back
      // to "seen just now" every time the phone's screen wakes.
      announcedAt: existing ? existing.announcedAt : at,
    };
    map.set(deviceId, entry);
    presenceBySocket.set(socketId, { userId, deviceId });
    return entry;
  };

  const withdraw = ({ userId, deviceId }) => {
    const map = presenceByUser.get(userId);
    const entry = map && map.get(deviceId);
    if (!entry) return false;
    map.delete(deviceId);
    presenceBySocket.delete(entry.socketId);
    return true;
  };

  const removeSocketPresence = (socketId) => {
    const located = presenceBySocket.get(socketId);
    if (!located) return null;
    presenceBySocket.delete(socketId);
    const map = presenceByUser.get(located.userId);
    const entry = map && map.get(located.deviceId);
    // Only drop the entry if it still points at this socket: a reconnect may
    // already have replaced it with a newer one.
    if (entry && entry.socketId === socketId) map.delete(located.deviceId);
    return located;
  };

  const listDevices = (userId) =>
    Array.from(devicesFor(userId).values()).map(publicDevice);

  const getEntry = (userId, deviceId) => devicesFor(userId).get(deviceId);

  const dropRequest = (request) => {
    pendingRequests.delete(request.requestId);
    pendingByDevice.delete(request.phoneDeviceId);
    pendingByDesktopId.delete(request.desktopId);
  };

  const createRequest = ({ userId, desktopId, desktopSocketId, phoneDeviceId, at }) => {
    const entry = devicesFor(userId).get(phoneDeviceId);
    // A device on another account is indistinguishable from one that does not
    // exist — deliberately, so the reason code cannot be used to probe for
    // other accounts' devices.
    if (!entry) return { ok: false, reason: 'DEVICE_GONE' };
    if (linkByDesktopId.has(desktopId)) return { ok: false, reason: 'ALREADY_LINKED' };
    if (pendingByDesktopId.has(desktopId)) return { ok: false, reason: 'ALREADY_LINKED' };
    if (isBusy(phoneDeviceId)) return { ok: false, reason: 'DEVICE_BUSY' };

    const request = {
      requestId: newId(),
      userId,
      desktopId,
      desktopSocketId,
      phoneDeviceId,
      phoneSocketId: entry.socketId,
      expiresAt: at + requestTtlMs,
    };
    pendingRequests.set(request.requestId, request);
    pendingByDevice.set(phoneDeviceId, request.requestId);
    pendingByDesktopId.set(desktopId, request.requestId);
    return { ok: true, request };
  };

  const indexLink = (link) => {
    links.set(link.linkId, link);
    linkByDesktopId.set(link.desktopId, link.linkId);
    linkByPhoneDeviceId.set(link.phoneDeviceId, link.linkId);
    linkBySocketId.set(link.desktopSocketId, link.linkId);
    linkBySocketId.set(link.phoneSocketId, link.linkId);
  };

  const resolveRequest = (requestId, accept, at) => {
    const request = pendingRequests.get(requestId);
    if (!request) return { ok: false, reason: 'REQUEST_UNKNOWN' };
    dropRequest(request);

    if (!accept) return { ok: true, accepted: false, request };

    const entry = devicesFor(request.userId).get(request.phoneDeviceId);
    if (!entry) return { ok: false, reason: 'DEVICE_GONE' };

    const link = {
      linkId: newId(),
      userId: request.userId,
      desktopId: request.desktopId,
      desktopSocketId: request.desktopSocketId,
      phoneDeviceId: request.phoneDeviceId,
      phoneSocketId: entry.socketId,
      examProblems: [],
      createdAt: at,
      desktopGraceUntil: null,
      phoneGraceUntil: null,
    };
    indexLink(link);
    return { ok: true, accepted: true, link, request };
  };

  const cancelRequest = (requestId) => {
    const request = pendingRequests.get(requestId);
    if (!request) return null;
    dropRequest(request);
    return request;
  };

  const sweepRequests = (at) => {
    const expired = [];
    for (const request of pendingRequests.values()) {
      if (request.expiresAt <= at) expired.push(request);
    }
    expired.forEach(dropRequest);
    return expired;
  };

  const getLink = (linkId) => links.get(linkId);
  const getLinkByDesktopId = (desktopId) => links.get(linkByDesktopId.get(desktopId));
  const getLinkByPhoneDeviceId = (deviceId) => links.get(linkByPhoneDeviceId.get(deviceId));
  const getLinkBySocketId = (socketId) => links.get(linkBySocketId.get(socketId));

  const setExamProblems = (linkId, problems) => {
    const link = links.get(linkId);
    if (!link) return null;
    link.examProblems = problems;
    return link;
  };

  const endLink = (linkId) => {
    const link = links.get(linkId);
    if (!link) return null;
    links.delete(linkId);
    linkByDesktopId.delete(link.desktopId);
    linkByPhoneDeviceId.delete(link.phoneDeviceId);
    linkBySocketId.delete(link.desktopSocketId);
    linkBySocketId.delete(link.phoneSocketId);
    return link;
  };

  const markSocketGone = (socketId, at) => {
    const link = getLinkBySocketId(socketId);
    if (!link) return null;
    if (link.desktopSocketId === socketId) {
      link.desktopGraceUntil = at + graceMs;
      return { link, side: 'desktop' };
    }
    link.phoneGraceUntil = at + graceMs;
    return { link, side: 'phone' };
  };

  const reattachDesktop = ({ userId, desktopId, socketId }) => {
    const link = getLinkByDesktopId(desktopId);
    if (!link || link.userId !== userId) return null;
    linkBySocketId.delete(link.desktopSocketId);
    link.desktopSocketId = socketId;
    link.desktopGraceUntil = null;
    linkBySocketId.set(socketId, link.linkId);
    return link;
  };

  const reattachPhone = ({ userId, deviceId, socketId }) => {
    const link = getLinkByPhoneDeviceId(deviceId);
    if (!link || link.userId !== userId) return null;
    linkBySocketId.delete(link.phoneSocketId);
    link.phoneSocketId = socketId;
    link.phoneGraceUntil = null;
    linkBySocketId.set(socketId, link.linkId);
    return link;
  };

  const sweepGrace = (at) => {
    const ended = [];
    for (const link of Array.from(links.values())) {
      const desktopExpired = link.desktopGraceUntil !== null && link.desktopGraceUntil <= at;
      const phoneExpired = link.phoneGraceUntil !== null && link.phoneGraceUntil <= at;
      if (!desktopExpired && !phoneExpired) continue;
      endLink(link.linkId);
      ended.push({ link, side: desktopExpired ? 'desktop' : 'phone' });
    }
    return ended;
  };

  return {
    announce,
    withdraw,
    removeSocketPresence,
    listDevices,
    getEntry,
    createRequest,
    resolveRequest,
    cancelRequest,
    sweepRequests,
    getLink,
    getLinkByDesktopId,
    getLinkByPhoneDeviceId,
    getLinkBySocketId,
    setExamProblems,
    endLink,
    markSocketGone,
    reattachDesktop,
    reattachPhone,
    sweepGrace,
  };
};

module.exports = { createRegistry, DEFAULT_REQUEST_TTL_MS, DEFAULT_GRACE_MS };
