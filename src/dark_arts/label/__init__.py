"""Build the labeled positive set.

Cross-references parsed Form 4 grants with extracted DEFM14A/S-4 deal
timelines. A grant in ``[first_contact, announced - 1d]`` is a Tier-1/2/3
MNPI-adjacent positive depending on what stage of the deal it overlaps.
See ``docs/plan.md`` §8 (Labeled Dataset Strategy).
"""
