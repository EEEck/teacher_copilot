"""Shared fixtures for wiki package tests."""

from pathlib import Path

CLASS_ID = "chemie_9b_2026_27"
SEED_WIKI = Path(__file__).resolve().parent.parent / "teacher_wiki"

DIARY = """# Lesson Results — 2026-10-01 — Test Lesson

## What was covered
- Topic A
- Topic B

## Student participation
- Active class discussion

## What went well
- Good engagement

## What didn't go well
- Rushed ending

## Student observations
- S-014: Excellent
- S-021: Needed help

## Homework & follow-ups
- Homework: Sheet 3
- Next: Review Topic A
"""
