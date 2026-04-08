import type { ScoredPlace } from '../types';

const STORAGE_KEY = 'foodie_selected_places';

export interface StoredSelection {
  place: ScoredPlace;
  selected_at: number; // timestamp ms
  user_id: string;
}

export const storageService = {
  /** Load all saved selections from localStorage */
  load(): StoredSelection[] {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : [];
    } catch {
      return [];
    }
  },

  /** Save a new selection to localStorage */
  save(place: ScoredPlace, user_id: string): StoredSelection[] {
    const existing = this.load();

    // Avoid duplicate place_id for same user
    const filtered = existing.filter(
      (s) => !(s.place.place_id === place.place_id && s.user_id === user_id),
    );

    const entry: StoredSelection = {
      place,
      selected_at: Date.now(),
      user_id,
    };

    const updated = [entry, ...filtered];
    localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
    return updated;
  },

  /** Remove a specific selection by place_id + user_id */
  remove(place_id: string, user_id: string): StoredSelection[] {
    const updated = this.load().filter(
      (s) => !(s.place.place_id === place_id && s.user_id === user_id),
    );
    localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
    return updated;
  },

  /** Clear all selections for a user */
  clearUser(user_id: string): StoredSelection[] {
    const updated = this.load().filter((s) => s.user_id !== user_id);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
    return updated;
  },

  /** Clear everything */
  clearAll(): void {
    localStorage.removeItem(STORAGE_KEY);
  },
};
