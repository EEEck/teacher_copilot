/**
 * Browser-local teacher checklist for class home.
 * Durability is localStorage only — not synced to the wiki or backend.
 */

export type ClassHomeNote = {
  id: string;
  text: string;
  done: boolean;
};

export function classHomeNotesKey(classId: string): string {
  return `kp:class-notes:${classId}`;
}

type NotesStorage = Pick<Storage, "getItem" | "setItem" | "removeItem">;

export function loadClassHomeNotes(
  storage: NotesStorage,
  classId: string,
): ClassHomeNote[] {
  const raw = storage.getItem(classHomeNotesKey(classId));
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(isClassHomeNote);
  } catch {
    return [];
  }
}

export function saveClassHomeNotes(
  storage: NotesStorage,
  classId: string,
  notes: ClassHomeNote[],
): void {
  storage.setItem(classHomeNotesKey(classId), JSON.stringify(notes));
}

export function addClassHomeNote(
  notes: ClassHomeNote[],
  text: string,
): ClassHomeNote[] {
  const trimmed = text.trim();
  if (!trimmed) return notes;
  return [
    ...notes,
    {
      id:
        typeof crypto !== "undefined" && "randomUUID" in crypto
          ? crypto.randomUUID()
          : `note-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      text: trimmed,
      done: false,
    },
  ];
}

export function toggleClassHomeNote(
  notes: ClassHomeNote[],
  id: string,
): ClassHomeNote[] {
  return notes.map((note) =>
    note.id === id ? { ...note, done: !note.done } : note,
  );
}

export function deleteClassHomeNote(
  notes: ClassHomeNote[],
  id: string,
): ClassHomeNote[] {
  return notes.filter((note) => note.id !== id);
}

function isClassHomeNote(value: unknown): value is ClassHomeNote {
  if (!value || typeof value !== "object") return false;
  const note = value as ClassHomeNote;
  return (
    typeof note.id === "string" &&
    typeof note.text === "string" &&
    typeof note.done === "boolean"
  );
}
