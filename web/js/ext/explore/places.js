// Save only municipality IDs; recent visits stay in this page's memory.
export const SAVED_KEY = "nc-saved-places-v1";
const MAX_SAVED = 30, MAX_RECENT = 12;
export function placeLists(valid, storage) {
  let saved = [], recent = [], persistent = !!storage;
  const ids = values => [...new Set(Array.isArray(values) ? values.filter(id => typeof id === "string" && valid(id)) : [])];
  try { saved = ids(JSON.parse(storage?.getItem(SAVED_KEY) || "[]")).slice(0, MAX_SAVED); }
  catch { persistent = false; }
  function persist() {
    if (!storage) return;
    try { storage.setItem(SAVED_KEY, JSON.stringify(saved)); persistent = true; }
    catch { persistent = false; }
  }
  function remove(id) {
    if (!saved.includes(id)) return false;
    saved = saved.filter(x => x !== id);
    persist();
    return true;
  }
  return {
    get saved() { return saved.slice(); },
    get recent() { return recent.slice(); },
    get persistent() { return persistent; },
    maxSaved:MAX_SAVED,
    has:id => saved.includes(id),
    toggle(id) {
      if (saved.includes(id)) { remove(id); return false; }
      if (typeof id !== "string" || !valid(id) || saved.length >= MAX_SAVED) return false;
      saved = [id,...saved]; persist(); return true;
    },
    remove,
    visit(id) {
      if (typeof id === "string" && valid(id)) recent = [id,...recent.filter(x => x !== id)].slice(0, MAX_RECENT);
    },
    clearRecent() { recent = []; },
  };
}
