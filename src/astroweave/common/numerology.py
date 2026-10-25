"""Deterministic Pythagorean numerology from a name and birth date.

No LLM and no chart service — pure arithmetic over the standard Pythagorean
letter values (A=1..I=9, repeating), with traditional keyword meanings and the
master numbers 11/22/33 preserved. This lets the app give an instant, free
reading even when the chart engine is asleep.

Numerology is a classical/esoteric system, not science. The numbers here are
computed by the common Pythagorean method; the UI states the limits and that a
professional numerologist should be consulted for a personal reading.
"""

from __future__ import annotations

from datetime import datetime, timezone

_VOWELS = set("AEIOU")
_MASTER = {11, 22, 33}

# Standard keyword meanings for each reduced number.
MEANINGS: dict[int, str] = {
    1: "the Leader — independent, driven, original",
    2: "the Diplomat — cooperative, sensitive, a peacemaker",
    3: "the Communicator — expressive, creative, sociable",
    4: "the Builder — practical, disciplined, dependable",
    5: "the Explorer — adventurous, adaptable, freedom-loving",
    6: "the Nurturer — responsible, caring, home- and family-centred",
    7: "the Seeker — analytical, introspective, spiritual",
    8: "the Achiever — ambitious, organised, drawn to mastery and success",
    9: "the Humanitarian — compassionate, idealistic, generous",
    11: "the Intuitive (master number) — inspired, visionary, highly sensitive",
    22: "the Master Builder (master number) — large visions made concrete",
    33: "the Master Teacher (master number) — selfless, nurturing, uplifting",
}

# Themes for the Personal Year (a 9-year cycle, so reduced to 1–9).
PERSONAL_YEAR_MEANING: dict[int, str] = {
    1: "a year of fresh starts, initiative and new beginnings",
    2: "a year of patience, relationships and cooperation",
    3: "a year of creativity, self-expression and social growth",
    4: "a year of hard work, foundations and discipline",
    5: "a year of change, freedom and new experiences",
    6: "a year of responsibility, home and service to others",
    7: "a year of reflection, study and inner growth",
    8: "a year of achievement, finances and recognition",
    9: "a year of completion, letting go and transition",
}


def _reduce(n: int, keep_master: bool = True) -> int:
    """Reduce to a single digit, preserving master numbers 11/22/33."""
    while n > 9 and not (keep_master and n in _MASTER):
        n = sum(int(digit) for digit in str(n))
    return n


def _letter_value(char: str) -> int:
    """Pythagorean value of an uppercase A–Z letter (A=1..I=9, J=1.., S=1..)."""
    return ((ord(char) - 65) % 9) + 1


def life_path(birth_date: str) -> int:
    """Life Path from a 'YYYY-MM-DD' date (reduce each part, then sum)."""
    year, month, day = birth_date.split("-")
    parts = [
        _reduce(sum(int(ch) for ch in year)),
        _reduce(int(month)),
        _reduce(int(day)),
    ]
    return _reduce(sum(parts))


def birthday_number(birth_date: str) -> int:
    return _reduce(int(birth_date.split("-")[2]))


def _name_sum(name: str, which: str) -> int:
    total = 0
    for char in name.upper():
        if "A" <= char <= "Z":
            is_vowel = char in _VOWELS
            if which == "all" or (which == "vowels" and is_vowel) or (which == "consonants" and not is_vowel):
                total += _letter_value(char)
    return _reduce(total)


def expression(name: str) -> int:
    """Expression / Destiny number — all letters of the full name."""
    return _name_sum(name, "all")


def soul_urge(name: str) -> int:
    """Soul Urge / Heart's Desire — the vowels of the name."""
    return _name_sum(name, "vowels")


def personality(name: str) -> int:
    """Personality number — the consonants of the name."""
    return _name_sum(name, "consonants")


def maturity(name: str, birth_date: str) -> int:
    """Maturity number — Life Path + Expression, the direction later life matures toward."""
    return _reduce(life_path(birth_date) + expression(name))


def personal_year(birth_date: str, year: int | None = None) -> int:
    """Personal Year — birth month + birth day + the current year, reduced to 1–9."""
    _, month, day = birth_date.split("-")
    if year is None:
        year = datetime.now(timezone.utc).year
    total = _reduce(int(month)) + _reduce(int(day)) + _reduce(sum(int(ch) for ch in str(year)))
    return _reduce(total, keep_master=False)


def build_numerology(name: str, birth_date: str) -> dict:
    """Assemble the core numbers with their meanings and a plain 'about' line.

    Name-based numbers are omitted (number 0) if the name has no letters.
    """
    def entry(number: int, about: str) -> dict:
        return {"number": number, "meaning": MEANINGS.get(number, ""), "about": about}

    py = personal_year(birth_date)
    has_letters = any("A" <= c <= "Z" for c in (name or "").upper())
    core = {
        "life_path": entry(life_path(birth_date), "Your life's main direction and lessons — from your birth date."),
        "personal_year": {
            "number": py,
            "meaning": PERSONAL_YEAR_MEANING.get(py, ""),
            "about": "The theme of your current year in the 9-year cycle — from your birthday and this year.",
        },
        "birthday": entry(birthday_number(birth_date), "A particular gift you carry — from the day of the month you were born."),
    }
    if has_letters:
        core["expression"] = entry(expression(name), "Your natural talents and abilities — from your full name.")
        core["soul_urge"] = entry(soul_urge(name), "What inwardly motivates you (your heart's desire) — from the vowels of your name.")
        core["personality"] = entry(personality(name), "How others first perceive you — from the consonants of your name.")
        core["maturity"] = entry(maturity(name, birth_date), "The direction your later life matures toward — Life Path and Expression combined.")
    return {"name_used": name, "method": "Pythagorean", "numbers": core}
