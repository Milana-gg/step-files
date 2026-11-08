"""Проверяем сами тестовые модели напрямую через OCC (чужой код не нужен).

Если эти тесты падают — ошибка в генераторе, а не у других участников.
"""
from __future__ import annotations

import math
from pathlib import Path

import pytest

from tests.generate_models import BOX_SIZE, HOLE_RADIUS, PAIRS, SHIFT_VECTOR

pytest.importorskip("OCC.Core.gp", reason="pythonocc-core не установлен")

from OCC.Core.GProp import GProp_GProps  # noqa: E402
from OCC.Core.IFSelect import IFSelect_RetDone  # noqa: E402
from OCC.Core.STEPControl import STEPControl_Reader  # noqa: E402


def _volume_props(shape: object) -> GProp_GProps:
    props = GProp_GProps()
    try:
        from OCC.Core.BRepGProp import brepgprop

        brepgprop.VolumeProperties(shape, props)
    except ImportError:
        from OCC.Core.BRepGProp import brepgprop_VolumeProperties

        brepgprop_VolumeProperties(shape, props)
    return props


def _read_step(path: Path) -> object | None:
    reader = STEPControl_Reader()
    if reader.ReadFile(str(path)) != IFSelect_RetDone:
        return None
    reader.TransferRoots()
    return reader.OneShape() if reader.NbShapes() else None


def test_all_files_created(pairs: dict[str, tuple[Path, Path]]) -> None:
    assert set(pairs) == {p.name for p in PAIRS}
    for a, b in pairs.values():
        assert a.exists() and b.exists()


def test_box_volume(pairs: dict[str, tuple[Path, Path]]) -> None:
    shape = _read_step(pairs["identical"][0])
    assert shape is not None
    expected = BOX_SIZE[0] * BOX_SIZE[1] * BOX_SIZE[2]
    assert _volume_props(shape).Mass() == pytest.approx(expected, rel=1e-6)


def test_hole_volume(pairs: dict[str, tuple[Path, Path]]) -> None:
    shape = _read_step(pairs["hole"][1])
    assert shape is not None
    box = BOX_SIZE[0] * BOX_SIZE[1] * BOX_SIZE[2]
    hole = math.pi * HOLE_RADIUS**2 * BOX_SIZE[2]
    assert _volume_props(shape).Mass() == pytest.approx(box - hole, rel=1e-6)


def test_shifted_keeps_volume_but_moves_center(pairs: dict[str, tuple[Path, Path]]) -> None:
    a, b = _read_step(pairs["shifted"][0]), _read_step(pairs["shifted"][1])
    assert a is not None and b is not None
    pa, pb = _volume_props(a), _volume_props(b)
    assert pa.Mass() == pytest.approx(pb.Mass(), rel=1e-9)
    assert pb.CentreOfMass().X() - pa.CentreOfMass().X() == pytest.approx(SHIFT_VECTOR[0], abs=1e-6)


def test_broken_files_are_not_readable(pairs: dict[str, tuple[Path, Path]]) -> None:
    assert _read_step(pairs["damaged"][1]) is None
    assert _read_step(pairs["empty"][1]) is None


def test_brep_file_is_not_empty(pairs: dict[str, tuple[Path, Path]]) -> None:
    assert pairs["step_vs_brep"][1].stat().st_size > 0
