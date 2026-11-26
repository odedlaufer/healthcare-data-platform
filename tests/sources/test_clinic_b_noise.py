"""FR-SRC3: Clinic B noise is seeded, changes only what it reports, and follows its rates."""

import random
from dataclasses import fields
from datetime import date

import pytest

from sources.clinic_b.nicknames import NICKNAMES
from sources.clinic_b.noise import (
    NOISE_LEVELS,
    Demographics,
    Noise,
    NoiseKind,
    NoiseRates,
    address_change,
    apply_noise,
    missing_phone,
    nickname,
    transposed_date,
    typo,
)

AS_OF = date(2026, 11, 1)
ALL = NoiseRates(typo=1, nickname=1, address_change=1, transposed_date=1, missing_phone=1)
NONE = NoiseRates(typo=0, nickname=0, address_change=0, transposed_date=0, missing_phone=0)


def _patient(**overrides: object) -> Demographics:
    values: dict[str, object] = {
        "given_name": "William",
        "family_name": "Hartmann",
        "birth_date": date(1987, 3, 9),
        "sex": "male",
        "address_line": "12 Elm St",
        "city": "Worcester",
        "state": "MA",
        "postal_code": "01608",
        "phone": "555-201-3344",
    }
    values.update(overrides)
    return Demographics(**values)  # type: ignore[arg-type]


def _changed_fields(before: Demographics, after: Demographics) -> set[str]:
    return {
        f.name for f in fields(Demographics) if getattr(before, f.name) != getattr(after, f.name)
    }


def _value(record: Demographics, field: str) -> str:
    value = getattr(record, field)
    if value is None:
        return ""
    return value.isoformat() if isinstance(value, date) else str(value)


# --- rates -------------------------------------------------------------------------------


@pytest.mark.parametrize("bad", [-0.01, 1.01])
def test_rates_must_be_probabilities(bad: float) -> None:
    with pytest.raises(ValueError, match="typo rate"):
        NoiseRates(typo=bad, nickname=0, address_change=0, transposed_date=0, missing_phone=0)


def test_noise_levels_increase_for_every_kind() -> None:
    low, medium, high = (NOISE_LEVELS[level] for level in ("low", "medium", "high"))
    for kind in NoiseKind:
        assert low.rate(kind) < medium.rate(kind) < high.rate(kind)


# --- apply_noise -------------------------------------------------------------------------


def test_zero_rates_change_nothing() -> None:
    patient = _patient()
    assert apply_noise(patient, NONE, random.Random(1), AS_OF) == (patient, ())


def test_all_rates_apply_every_kind() -> None:
    _, applied = apply_noise(_patient(), ALL, random.Random(1), AS_OF)
    assert {noise.kind for noise in applied} == set(NoiseKind)


@pytest.mark.parametrize("seed", range(50))
def test_same_seed_same_output(seed: int) -> None:
    rates = NOISE_LEVELS["high"]
    first = apply_noise(_patient(), rates, random.Random(seed), AS_OF)
    second = apply_noise(_patient(), rates, random.Random(seed), AS_OF)
    assert first == second


@pytest.mark.parametrize("seed", range(200))
def test_reported_noise_explains_every_change(seed: int) -> None:
    patient = _patient()
    noisy, applied = apply_noise(patient, ALL, random.Random(seed), AS_OF)
    assert _changed_fields(patient, noisy) == {noise.field for noise in applied}
    # Two kinds can touch one field (nickname, then a typo in it): the entries chain in order.
    current = {f.name: _value(patient, f.name) for f in fields(Demographics)}
    for noise in applied:
        assert noise.before == current[noise.field]
        current[noise.field] = noise.after
    assert current == {f.name: _value(noisy, f.name) for f in fields(Demographics)}
    assert noisy.sex == patient.sex
    assert (noisy.city, noisy.state, noisy.postal_code) == ("Worcester", "MA", "01608")


def test_kind_that_cannot_apply_is_not_reported() -> None:
    patient = _patient(given_name="Zephyrine", phone=None, birth_date=date(1988, 5, 20))
    rates = NoiseRates(typo=0, nickname=1, address_change=0, transposed_date=1, missing_phone=1)
    assert apply_noise(patient, rates, random.Random(3), AS_OF) == (patient, ())


@pytest.mark.parametrize("kind", list(NoiseKind))
def test_observed_rate_matches_configured_rate(kind: NoiseKind) -> None:
    rate = 0.3
    rates = NoiseRates(**{k.value: (rate if k is kind else 0.0) for k in NoiseKind})
    rng = random.Random(20261101)
    trials = 4000
    hits = sum(bool(apply_noise(_patient(), rates, rng, AS_OF)[1]) for _ in range(trials))
    assert abs(hits / trials - rate) < 0.03


# --- individual kinds --------------------------------------------------------------------


@pytest.mark.parametrize("seed", range(300))
def test_typo_is_one_small_edit_that_keeps_the_first_letter(seed: int) -> None:
    patient = _patient()
    result = typo(patient, random.Random(seed))
    assert result is not None
    _, noise = result
    assert noise.kind is NoiseKind.TYPO
    assert noise.after != noise.before
    assert abs(len(noise.after) - len(noise.before)) <= 1
    assert noise.after[0] == noise.before[0] or noise.after[0].isupper()
    assert noise.after.isalpha()


def test_typo_skips_names_too_short_to_change() -> None:
    patient = _patient(given_name="Al", family_name="Li")
    assert all(typo(patient, random.Random(seed)) is None for seed in range(20))


def test_nickname_comes_from_the_table() -> None:
    result = nickname(_patient(given_name="William"), random.Random(0))
    assert result is not None
    noisy, noise = result
    assert noisy.given_name in NICKNAMES["william"]
    assert (noise.before, noise.after) == ("William", noisy.given_name)


def test_nickname_needs_a_known_name() -> None:
    assert nickname(_patient(given_name="Zephyrine"), random.Random(0)) is None


def test_nickname_table_keys_are_lower_case_and_values_title_case() -> None:
    for formal, options in NICKNAMES.items():
        assert formal == formal.lower()
        assert options
        assert all(option == option.title() for option in options)


@pytest.mark.parametrize("seed", range(50))
def test_address_change_moves_within_town(seed: int) -> None:
    patient = _patient()
    noisy, noise = address_change(patient, random.Random(seed)) or (patient, None)
    assert noise is not None
    assert noisy.address_line != patient.address_line
    assert noise == Noise(NoiseKind.ADDRESS_CHANGE, "address_line", "12 Elm St", noisy.address_line)


def test_transposed_date_swaps_day_and_month() -> None:
    patient = _patient(birth_date=date(1988, 3, 9))
    noisy, _ = transposed_date(patient, random.Random(0), AS_OF) or (patient, None)
    assert noisy.birth_date == date(1988, 9, 3)


def test_transposed_date_swaps_year_digits_only_downwards() -> None:
    older = transposed_date(_patient(birth_date=date(1987, 5, 20)), random.Random(0), AS_OF)
    assert older is not None
    assert older[0].birth_date == date(1978, 5, 20)
    assert transposed_date(_patient(birth_date=date(1978, 5, 20)), random.Random(0), AS_OF) is None


def test_transposed_date_never_goes_past_as_of() -> None:
    patient = _patient(birth_date=date(2026, 1, 11))
    assert transposed_date(patient, random.Random(0), date(2026, 6, 1)) is None


def test_transposed_date_keeps_leap_day_valid() -> None:
    patient = _patient(birth_date=date(1996, 2, 29))
    assert transposed_date(patient, random.Random(0), AS_OF) is None
    leap = transposed_date(
        _patient(birth_date=date(2084, 2, 29)), random.Random(0), date(2100, 1, 1)
    )
    assert leap is not None
    assert leap[0].birth_date == date(2048, 2, 29)


def test_missing_phone_clears_it() -> None:
    noisy, noise = missing_phone(_patient(), random.Random(0)) or (_patient(), None)
    assert noisy.phone is None
    assert noise == Noise(NoiseKind.MISSING_PHONE, "phone", "555-201-3344", "")
    assert missing_phone(_patient(phone=None), random.Random(0)) is None
