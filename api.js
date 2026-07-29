/**
 * api.js
 * Shared helper for talking to the Study Group Matcher backend.
 * Matches the endpoints implemented on the backend/api branch:
 *   GET  /api/match/ping
 *   POST /api/match/confirm
 *   GET  /api/auth/google/login
 *   GET  /api/auth/notion/login
 * Change API_BASE if the backend is not running on localhost:5000.
 */

const API_BASE = "http://localhost:5000";
const PROFILE_STORAGE_KEY = "studyProfile";

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

function googleLoginUrl() {
    return API_BASE + "/api/auth/google/login";
}

function notionLoginUrl() {
    return API_BASE + "/api/auth/notion/login";
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
