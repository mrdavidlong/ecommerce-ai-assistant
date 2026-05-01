const STORAGE_KEY = "current_user";
const CHAT_SESSION_KEY = "chat_session_id";
export const AUTH_CHANGED_EVENT = "auth-changed";

export interface CurrentUser {
  id: string;
  name: string;
}

export function getCurrentUser(): CurrentUser | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as CurrentUser;
  } catch {
    return null;
  }
}

export function setCurrentUser(user: CurrentUser): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(user));
  window.dispatchEvent(new CustomEvent(AUTH_CHANGED_EVENT));
}

export function clearCurrentUser(): void {
  localStorage.removeItem(STORAGE_KEY);
  localStorage.removeItem(CHAT_SESSION_KEY);
  window.dispatchEvent(new CustomEvent(AUTH_CHANGED_EVENT));
}
