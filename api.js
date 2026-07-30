/**
 * api.js
 * Shared helper for talking to the Study Group Matcher backend.
 * Matches the endpoints implemented on the backend/api branch:
 *   GET  /api/match/ping
 *   POST /api/match/confirm          -- proposes a pending match, books nothing yet
 *   POST /api/match/<id>/respond     -- invited partner accepts/declines; booking happens on accept
 *   POST /api/match/<id>/cancel      -- either participant cancels a confirmed match
 *   GET  /api/match/pending?user_id= -- invites waiting on this user to respond to
 *   GET  /api/match/sent?user_id=    -- invites this user sent that are still awaiting a response
 *   GET  /api/match/candidates?user_id=
 *   GET  /api/match/history?user_id=
 *   POST /api/users
 *   GET  /api/users/<id>/connections
 *   GET  /api/auth/google/login[?user_id=]
 *   GET  /api/auth/notion/login[?user_id=]
 * Change API_BASE if the backend is not running on localhost:5000.
 */

const API_BASE = "http://localhost:5000";
const PROFILE_STORAGE_KEY = "studyProfile";
const USER_ID_STORAGE_KEY = "studyUserId";

function getStoredProfile() {
    try {
          const raw = localStorage.getItem(PROFILE_STORAGE_KEY);
          return raw ? JSON.parse(raw) : null;
    } catch (err) {
          console.error("Could not read stored profile", err);
          return null;
    }
}

function saveProfile(profile) {
    localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(profile));
}

function renderCurrentUserBadge(elementId) {
    var el = document.getElementById(elementId || "current-user-note");
    if (!el) return;
    var profile = getStoredProfile();
    el.textContent = profile && profile.name ? "Logged in as " + profile.name : "No profile yet";
}

function getStoredUserId() {
    const raw = localStorage.getItem(USER_ID_STORAGE_KEY);
    return raw ? Number(raw) : null;
}

function saveUserId(userId) {
    localStorage.setItem(USER_ID_STORAGE_KEY, String(userId));
}

function googleLoginUrl(userId) {
    const url = API_BASE + "/api/auth/google/login";
    return userId ? url + "?user_id=" + encodeURIComponent(userId) : url;
}

function notionLoginUrl(userId) {
    const url = API_BASE + "/api/auth/notion/login";
    return userId ? url + "?user_id=" + encodeURIComponent(userId) : url;
}

async function pingBackend() {
    try {
          const res = await fetch(API_BASE + "/api/match/ping");
          return res.ok;
    } catch (err) {
          return false;
    }
}

async function confirmMatch(payload) {
    const res = await fetch(API_BASE + "/api/match/confirm", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
    });

  let data = {};
    try {
          data = await res.json();
    } catch (err) {
          data = {};
    }

  return { ok: res.ok, status: res.status, data: data };
}

async function saveProfileToBackend(profile) {
    const res = await fetch(API_BASE + "/api/users", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(profile),
    });

    let data = {};
    try {
          data = await res.json();
    } catch (err) {
          data = {};
    }

    return { ok: res.ok, status: res.status, data: data };
}

async function getMatchCandidates(userId) {
    const res = await fetch(API_BASE + "/api/match/candidates?user_id=" + encodeURIComponent(userId));

    let data = {};
    try {
          data = await res.json();
    } catch (err) {
          data = {};
    }

    return { ok: res.ok, status: res.status, data: data };
}

async function getConnections(userId) {
    const res = await fetch(API_BASE + "/api/users/" + encodeURIComponent(userId) + "/connections");

    let data = {};
    try {
          data = await res.json();
    } catch (err) {
          data = {};
    }

    return { ok: res.ok, status: res.status, data: data };
}

async function getMatchHistory(userId) {
    const res = await fetch(API_BASE + "/api/match/history?user_id=" + encodeURIComponent(userId));

    let data = {};
    try {
          data = await res.json();
    } catch (err) {
          data = {};
    }

    return { ok: res.ok, status: res.status, data: data };
}

async function getPendingMatches(userId) {
    const res = await fetch(API_BASE + "/api/match/pending?user_id=" + encodeURIComponent(userId));

    let data = {};
    try {
          data = await res.json();
    } catch (err) {
          data = {};
    }

    return { ok: res.ok, status: res.status, data: data };
}

async function respondToMatch(matchId, responseValue, respondingUserId) {
    const res = await fetch(API_BASE + "/api/match/" + encodeURIComponent(matchId) + "/respond", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ response: responseValue, responding_user_id: respondingUserId }),
    });

    let data = {};
    try {
          data = await res.json();
    } catch (err) {
          data = {};
    }

    return { ok: res.ok, status: res.status, data: data };
}

async function cancelMatch(matchId, userId) {
    const res = await fetch(API_BASE + "/api/match/" + encodeURIComponent(matchId) + "/cancel", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ user_id: userId }),
    });

    let data = {};
    try {
          data = await res.json();
    } catch (err) {
          data = {};
    }

    return { ok: res.ok, status: res.status, data: data };
}

async function getSentMatches(userId) {
    const res = await fetch(API_BASE + "/api/match/sent?user_id=" + encodeURIComponent(userId));

    let data = {};
    try {
          data = await res.json();
    } catch (err) {
          data = {};
    }

    return { ok: res.ok, status: res.status, data: data };
}
