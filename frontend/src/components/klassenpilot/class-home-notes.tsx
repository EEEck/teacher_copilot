"use client";

import { useEffect, useState } from "react";
import { XIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import {
  addClassHomeNote,
  deleteClassHomeNote,
  loadClassHomeNotes,
  saveClassHomeNotes,
  toggleClassHomeNote,
  type ClassHomeNote,
} from "@/lib/class-home-notes";

type ClassHomeNotesProps = {
  classId: string;
};

/**
 * Local teacher checklist for class home.
 * Persists in localStorage only (not wiki / backend).
 */
export function ClassHomeNotes({ classId }: ClassHomeNotesProps) {
  const [notes, setNotes] = useState<ClassHomeNote[]>([]);
  const [draft, setDraft] = useState("");
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setNotes(loadClassHomeNotes(window.localStorage, classId));
    setHydrated(true);
  }, [classId]);

  useEffect(() => {
    if (!hydrated) return;
    saveClassHomeNotes(window.localStorage, classId, notes);
  }, [classId, notes, hydrated]);

  const onAdd = () => {
    setNotes((current) => addClassHomeNote(current, draft));
    setDraft("");
  };

  return (
    <Card>
      <CardHeader className="pb-0">
        <CardTitle className="text-base">My notes</CardTitle>
        <p className="text-xs text-muted-foreground">
          Saved in this browser only.
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex gap-2">
          <Input
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="Add a quick todo…"
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                onAdd();
              }
            }}
            aria-label="New note"
          />
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onAdd}
            disabled={!draft.trim()}
          >
            Add
          </Button>
        </div>
        {notes.length === 0 ? (
          <p className="text-sm text-muted-foreground">No notes yet.</p>
        ) : (
          <ul className="space-y-2">
            {notes.map((note) => (
              <li key={note.id} className="flex items-start gap-2">
                <Checkbox
                  checked={note.done}
                  onCheckedChange={() =>
                    setNotes((current) => toggleClassHomeNote(current, note.id))
                  }
                  aria-label={note.done ? "Mark incomplete" : "Mark done"}
                  className="mt-0.5"
                />
                <span
                  className={
                    note.done
                      ? "flex-1 text-sm text-muted-foreground line-through"
                      : "flex-1 text-sm text-foreground"
                  }
                >
                  {note.text}
                </span>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-xs"
                  aria-label="Delete note"
                  onClick={() =>
                    setNotes((current) => deleteClassHomeNote(current, note.id))
                  }
                >
                  <XIcon />
                </Button>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
