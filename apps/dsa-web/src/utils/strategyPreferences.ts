const HOME_SELECTED_SKILLS_STORAGE_KEY = 'dsa.home.selectedAnalysisSkills';
export const MAX_HOME_ANALYSIS_SKILLS = 8;

function localStorageOrNull(): Storage | null {
  if (typeof window === 'undefined') return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export function readHomeSelectedSkillIds(): string[] {
  const storage = localStorageOrNull();
  if (!storage) return [];
  try {
    const raw = storage.getItem(HOME_SELECTED_SKILLS_STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return [...new Set(parsed.filter((id): id is string => typeof id === 'string' && id.trim().length > 0))]
      .slice(0, MAX_HOME_ANALYSIS_SKILLS);
  } catch {
    return [];
  }
}

export function writeHomeSelectedSkillIds(skillIds: string[]): void {
  const storage = localStorageOrNull();
  if (!storage) return;
  try {
    const normalized = [...new Set(skillIds.filter((id) => typeof id === 'string' && id.trim().length > 0))]
      .slice(0, MAX_HOME_ANALYSIS_SKILLS);
    if (normalized.length === 0) {
      storage.removeItem(HOME_SELECTED_SKILLS_STORAGE_KEY);
    } else {
      storage.setItem(HOME_SELECTED_SKILLS_STORAGE_KEY, JSON.stringify(normalized));
    }
  } catch {
    // Private browsing or a restricted WebView may disable local storage.
  }
}

export { HOME_SELECTED_SKILLS_STORAGE_KEY };
