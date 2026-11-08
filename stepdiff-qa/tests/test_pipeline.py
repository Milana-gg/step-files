"""Интеграционные тесты всей цепочки «загрузка → анализ → сравнение → отчёт».

Чужие модули вызываются через tests/adapters.py; пока их нет — тест пропускается.
Ожидания (match / differ / error) берутся из tests/generate_models.PAIRS.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.adapters import (
    LOADER_ERRORS,
    analyze,
    require,
    run_cli,
    run_pipeline,
    verdict_is_match,
)
from tests.generate_models import PAIRS

pytest.importorskip("OCC.Core.gp", reason="pythonocc-core не установлен")

OK_PAIRS = [p for p in PAIRS if p.expect in ("match", "differ")]
BAD_PAIRS = [p for p in PAIRS if p.expect == "error"]
EXIT_CODE = {"match": 0, "differ": 1, "error": 2}


# ---------- Python API: загрузка -> анализ -> сравнение ----------

@pytest.mark.parametrize("spec", OK_PAIRS, ids=lambda s: s.name)
def test_verdict(spec, pairs: dict[str, tuple[Path, Path]]) -> None:  # type: ignore[no-untyped-def]
    a, b = pairs[spec.name]
    result = run_pipeline(a, b)
    assert verdict_is_match(result) is (spec.expect == "match"), spec.description


@pytest.mark.parametrize("spec", BAD_PAIRS, ids=lambda s: s.name)
def test_broken_input_raises(spec, pairs: dict[str, tuple[Path, Path]]) -> None:  # type: ignore[no-untyped-def]
    a, b = pairs[spec.name]
    analyze(a)  # исходная модель должна грузиться нормально
    with pytest.raises(LOADER_ERRORS):  # noqa: PT011 — точные исключения даёт участник 4
        analyze(b)


def test_comparison_is_symmetric(pairs: dict[str, tuple[Path, Path]]) -> None:
    a, b = pairs["hole"]
    assert verdict_is_match(run_pipeline(a, b)) == verdict_is_match(run_pipeline(b, a))


def test_model_matches_itself(pairs: dict[str, tuple[Path, Path]]) -> None:
    a, _ = pairs["identical"]
    assert verdict_is_match(run_pipeline(a, a))


def test_tolerance_hides_tiny_difference(pairs: dict[str, tuple[Path, Path]]) -> None:
    """Огромный допуск должен сделать «отверстие» незаметным или хотя бы не ломать работу."""
    a, b = pairs["hole"]
    strict = verdict_is_match(run_pipeline(a, b, tol=1e-9))
    loose = verdict_is_match(run_pipeline(a, b, tol=1e9))
    assert strict is False
    assert loose is True


# ---------- CLI: коды возврата 0 / 1 / 2 ----------

@pytest.mark.parametrize("spec", PAIRS, ids=lambda s: s.name)
def test_cli_exit_code(spec, pairs: dict[str, tuple[Path, Path]]) -> None:  # type: ignore[no-untyped-def]
    a, b = pairs[spec.name]
    proc = run_cli(str(a), str(b), "--tol", "1e-6")
    assert proc.returncode == EXIT_CODE[spec.expect], proc.stderr


# ---------- Отчёты (участник 3) ----------

def test_json_report_is_valid(pairs: dict[str, tuple[Path, Path]], tmp_path: Path) -> None:
    a, b = pairs["hole"]
    result = run_pipeline(a, b)
    out = tmp_path / "report.json"
    require("report_json")(result, out)  # [Код участника 3]
    assert isinstance(json.loads(out.read_text(encoding="utf-8")), dict)


# ---------- Визуализация (участник 5) ----------

def test_plot_creates_png(pairs: dict[str, tuple[Path, Path]], tmp_path: Path) -> None:
    a, b = pairs["hole"]
    result = run_pipeline(a, b)
    out = tmp_path / "plot.png"
    require("plot")(a, b, result, out)  # [Код участника 5]
    assert out.exists() and out.stat().st_size > 0
