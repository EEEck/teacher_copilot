"""Default Update Memory trace scenario used by offline and live debug runs."""

from __future__ import annotations

CLASS_ID = "chemie_9b_2026_27"

MEMORY_UPDATE_PROMPTS = [
    """I want to update the lesson outcome from 05/29
""",
    """Lesson Results — 2026-05-29 —
What was covered
no problem on those two items:
Review common anions and their charges.
Separate ion charge from oxidation number.
I could not fully cover the following due to student confusin and interruption:
Connect chloride, oxide, and phosphate back to the redox sequence.
Student participation
student were engaged but too much confusion and student did not let me know early
What went well
they understood the common anions quickly, that concept was explained well by me
What didn't go well
went into a rabbit whole with phosphates and confused students too much
Student observations
Joonho was the only one who understood phosphate redox states he is doing very well, Alex was constantly interrupting and not following at all, Rita was participating well but not everything was correct
Homework & follow-ups
gave mainly homework about common anions
""",
    """I want to add more information about student participation:
Matt was also doing well and helped other students
with reguards to interruption that was mainly due to my poor lesson organization

in terms of open loops from 5-25,
I review metal displacement and student should have gotten that concept now, I had no time for the other open loop items

That is enough detail. Please make the lesson results ready to save memory.
""",
]
