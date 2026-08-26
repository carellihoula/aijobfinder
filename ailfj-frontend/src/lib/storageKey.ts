/**
 * Returns a localStorage key scoped to the current user.
 * The UID is held in memory (set by UserProvider on /users/me success) AND persisted
 * in localStorage as "ailfj_uid" so badge counts survive a page refresh without flashing.
 * "ailfj_uid" is the first 8 chars of the user UUID — not a credential, safe in localStorage.
 */
let _uid = localStorage.getItem("ailfj_uid") ?? "anon"

export function setStorageUid(uid: string): void {
  _uid = uid.slice(0, 8)
  localStorage.setItem("ailfj_uid", _uid)
}

export function scopedKey(key: string): string {
  return `${_uid}:${key}`
}
