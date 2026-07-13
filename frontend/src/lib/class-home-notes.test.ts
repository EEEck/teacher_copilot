import { describe, expect, it } from "vitest";

import {
  addClassHomeNote,
  classHomeNotesKey,
  deleteClassHomeNote,
  loadClassHomeNotes,
  saveClassHomeNotes,
  toggleClassHomeNote,
} from "./class-home-notes";

function memoryStorage() {
  const storage = new Map<string, string>();
  return {
    getItem: (key: string) => storage.get(key) ?? null,
    setItem: (key: string, value: string) => storage.set(key, value),
    removeItem: (key: string) => storage.delete(key),
  };
}

describe("class home notes", () => {
  it("persists notes under a class-scoped localStorage key", () => {
    const storage = memoryStorage();
    const notes = addClassHomeNote([], "Prep anion warm-up");
    saveClassHomeNotes(storage, "chemie_9b_2026_27", notes);
    expect(storage.getItem(classHomeNotesKey("chemie_9b_2026_27"))).toBeTruthy();
    expect(loadClassHomeNotes(storage, "chemie_9b_2026_27")).toEqual(notes);
  });

  it("adds, toggles, and deletes notes", () => {
    let notes = addClassHomeNote([], "  Call parents  ");
    expect(notes).toHaveLength(1);
    expect(notes[0].text).toBe("Call parents");
    expect(notes[0].done).toBe(false);

    notes = toggleClassHomeNote(notes, notes[0].id);
    expect(notes[0].done).toBe(true);

    notes = deleteClassHomeNote(notes, notes[0].id);
    expect(notes).toEqual([]);
  });

  it("ignores blank adds and corrupt storage", () => {
    expect(addClassHomeNote([], "   ")).toEqual([]);
    const storage = memoryStorage();
    storage.setItem(classHomeNotesKey("c1"), "{not-json");
    expect(loadClassHomeNotes(storage, "c1")).toEqual([]);
  });
});
