"""Default three-turn FCKW/CFC lesson-planning scenario prompts."""

CLASS_ID = "chemie_9b_2026_27"

PROMPT_TURN_1 = """Plan the next 45-minute lesson for Chemie 9b. Topic: redox reactions applied to CFC/FCKW compounds (Chlorfluorkohlenwasserstoffe). Include about 10 minutes on environmental impact (ozone layer, Montreal Protocol, alternatives). Build on our existing redox lessons in the wiki. Exam-oriented Gymnasium level.
Structure the lesson flow: 5 min redox recap, 15 min FCKW structure and redox half-reactions, 10 min environmental impact with one example (e.g. CFC-11), 10 min practice, 5 min exit ticket. Note the misconception: oxidation number vs charge.
Add differentiated practice and homework (2 questions). Teacher notes: no real CFCs in the lab; demo alternatives only."""

PROMPT_TURN_2 = """Can we also add a 5 min review session of the last 4 lectures? I would like to consider what the class confused the last few sessions and incorporate key findings to make the introduction of FCKW simpler for them to digest."""

PROMPT_TURN_3 = """I am very happy with it. Maybe as a last refinement, let's add only a 2 min recap together with students actively recalling the key learning."""

FCKW_PROMPTS = (PROMPT_TURN_1, PROMPT_TURN_2, PROMPT_TURN_3)
