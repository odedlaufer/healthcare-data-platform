"""Seeded noise for Clinic B patient demographics (FR-SRC3).

Each noise function takes a record and a ``random.Random`` and returns the changed record with
a ``Noise`` entry describing the change, or ``None`` when that kind of noise cannot apply to
the record (no nickname for the given name, no phone to drop). ``apply_noise`` applies every
kind at its configured rate. The generator stores each applied ``Noise`` with the ground-truth
link, so matching precision and recall can be broken down by noise kind.

All randomness comes from the ``rng`` argument: the same seed always gives the same output.
"""

import calendar
import random
from collections.abc import Callable, Mapping
from dataclasses import dataclass, fields, replace
from datetime import date
from enum import StrEnum

from sources.clinic_b.nicknames import NICKNAMES


@dataclass(frozen=True, slots=True)
class Demographics:
    """The identifying fields Clinic B shares with Hospital A."""

    given_name: str
    family_name: str
    birth_date: date
    sex: str
    address_line: str
    city: str
    state: str
    postal_code: str
    phone: str | None


class NoiseKind(StrEnum):
    TYPO = "typo"
    NICKNAME = "nickname"
    ADDRESS_CHANGE = "address_change"
    TRANSPOSED_DATE = "transposed_date"
    MISSING_PHONE = "missing_phone"


@dataclass(frozen=True, slots=True)
class Noise:
    """One applied change. ``after`` is empty when the value was removed."""

    kind: NoiseKind
    field: str
    before: str
    after: str


@dataclass(frozen=True, slots=True)
class NoiseRates:
    """Probability of applying each noise kind to one record."""

    typo: float
    nickname: float
    address_change: float
    transposed_date: float
    missing_phone: float

    def __post_init__(self) -> None:
        for item in fields(self):
            rate = getattr(self, item.name)
            if not 0.0 <= rate <= 1.0:
                raise ValueError(f"{item.name} rate must be between 0 and 1, got {rate}")

    def rate(self, kind: NoiseKind) -> float:
        rate: float = getattr(self, kind.value)
        return rate


# Three levels, so matching results are reported across noise levels (PRD risk: overfitting).
NOISE_LEVELS: Mapping[str, NoiseRates] = {
    "low": NoiseRates(
        typo=0.05, nickname=0.05, address_change=0.10, transposed_date=0.01, missing_phone=0.10
    ),
    "medium": NoiseRates(
        typo=0.15, nickname=0.10, address_change=0.20, transposed_date=0.03, missing_phone=0.25
    ),
    "high": NoiseRates(
        typo=0.30, nickname=0.20, address_change=0.35, transposed_date=0.06, missing_phone=0.40
    ),
}

NoiseResult = tuple[Demographics, Noise] | None

# QWERTY neighbours: realistic substitution typos.
_KEYBOARD_NEIGHBOURS: Mapping[str, str] = {
    "q": "wa",
    "w": "qeas",
    "e": "wrsd",
    "r": "etdf",
    "t": "ryfg",
    "y": "tugh",
    "u": "yihj",
    "i": "uojk",
    "o": "ipkl",
    "p": "ol",
    "a": "qwsz",
    "s": "awedxz",
    "d": "serfcx",
    "f": "drtgvc",
    "g": "ftyhbv",
    "h": "gyujnb",
    "j": "huikmn",
    "k": "jiolm",
    "l": "kop",
    "z": "asx",
    "x": "zsdc",
    "c": "xdfv",
    "v": "cfgb",
    "b": "vghn",
    "n": "bhjm",
    "m": "njk",
}

_STREET_NAMES = (
    "Maple",
    "Oak",
    "Pine",
    "Cedar",
    "Elm",
    "Washington",
    "Lincoln",
    "Park",
    "Lake",
    "Hill",
    "Main",
    "Church",
    "Spring",
    "Highland",
    "Summer",
)
_STREET_SUFFIXES = ("St", "Ave", "Rd", "Ln", "Dr", "Way", "Ct")


def _match_case(template: str, letter: str) -> str:
    return letter.upper() if template.isupper() else letter.lower()


def _typo_word(word: str, rng: random.Random) -> str | None:
    """Return ``word`` with one keyboard-style typo, or None if it is too short to change."""
    letters = [i for i, char in enumerate(word) if char.isalpha()]
    if len(letters) < 3:
        return None
    for _ in range(10):
        operation = rng.choice(("substitute", "delete", "insert", "transpose"))
        index = rng.choice(letters)
        char = word[index]
        if operation == "substitute":
            neighbour = rng.choice(_KEYBOARD_NEIGHBOURS.get(char.lower(), "e"))
            result = word[:index] + _match_case(char, neighbour) + word[index + 1 :]
        elif operation == "delete" and index != letters[0]:
            result = word[:index] + word[index + 1 :]
        elif operation == "insert":
            result = word[: index + 1] + char.lower() + word[index + 1 :]
        elif operation == "transpose" and index + 1 in letters and index != letters[0]:
            result = word[:index] + word[index + 1] + char + word[index + 2 :]
        else:
            continue
        if result != word:
            return result
    return None


def typo(record: Demographics, rng: random.Random) -> NoiseResult:
    """One keyboard typo in the given or family name; the first letter is never changed
    by deletion or transposition, as real typos rarely move it."""
    if rng.random() < 0.5:
        after = _typo_word(record.given_name, rng)
        if after is None:
            return None
        changed = replace(record, given_name=after)
        return changed, Noise(NoiseKind.TYPO, "given_name", record.given_name, after)
    after = _typo_word(record.family_name, rng)
    if after is None:
        return None
    changed = replace(record, family_name=after)
    return changed, Noise(NoiseKind.TYPO, "family_name", record.family_name, after)


def nickname(record: Demographics, rng: random.Random) -> NoiseResult:
    """Replace the given name with a common nickname, when one is known."""
    options = NICKNAMES.get(record.given_name.lower())
    if not options:
        return None
    after = rng.choice(options)
    return (
        replace(record, given_name=after),
        Noise(NoiseKind.NICKNAME, "given_name", record.given_name, after),
    )


def address_change(record: Demographics, rng: random.Random) -> NoiseResult:
    """The patient moved within the same town: new street line, same city and postal code."""
    while True:
        street = (
            f"{rng.randint(1, 9999)} {rng.choice(_STREET_NAMES)} {rng.choice(_STREET_SUFFIXES)}"
        )
        if street != record.address_line:
            break
    return (
        replace(record, address_line=street),
        Noise(NoiseKind.ADDRESS_CHANGE, "address_line", record.address_line, street),
    )


def transposed_date(record: Demographics, rng: random.Random, as_of: date) -> NoiseResult:
    """Swap day and month, or the last two digits of the birth year, keeping a valid date that
    is not later than ``as_of``. A year swap only ever moves the year earlier (1987 -> 1978)."""
    born = record.birth_date
    candidates: list[date] = []
    if born.day <= 12 and born.day != born.month:
        candidates.append(date(born.year, born.day, born.month))
    year = f"{born.year:04d}"
    swapped_year = int(year[:2] + year[3] + year[2])
    leap_day = born.month == 2 and born.day == 29
    if swapped_year < born.year and (not leap_day or calendar.isleap(swapped_year)):
        candidates.append(born.replace(year=swapped_year))
    candidates = [candidate for candidate in candidates if candidate <= as_of]
    if not candidates:
        return None
    after = rng.choice(candidates)
    return (
        replace(record, birth_date=after),
        Noise(NoiseKind.TRANSPOSED_DATE, "birth_date", born.isoformat(), after.isoformat()),
    )


def missing_phone(record: Demographics, rng: random.Random) -> NoiseResult:
    """Clinic B did not capture the phone number."""
    if record.phone is None:
        return None
    return (
        replace(record, phone=None),
        Noise(NoiseKind.MISSING_PHONE, "phone", record.phone, ""),
    )


def apply_noise(
    record: Demographics, rates: NoiseRates, rng: random.Random, as_of: date
) -> tuple[Demographics, tuple[Noise, ...]]:
    """Apply each noise kind at its rate, in a fixed order. Returns the noisy record and the
    changes actually applied (a drawn kind that cannot apply to the record adds nothing)."""
    steps: tuple[tuple[NoiseKind, Callable[[Demographics, random.Random], NoiseResult]], ...] = (
        (NoiseKind.NICKNAME, nickname),
        (NoiseKind.TYPO, typo),
        (NoiseKind.ADDRESS_CHANGE, address_change),
        (NoiseKind.TRANSPOSED_DATE, lambda r, g: transposed_date(r, g, as_of)),
        (NoiseKind.MISSING_PHONE, missing_phone),
    )
    applied: list[Noise] = []
    for kind, step in steps:
        if rng.random() >= rates.rate(kind):
            continue
        result = step(record, rng)
        if result is not None:
            record, noise = result
            applied.append(noise)
    return record, tuple(applied)
