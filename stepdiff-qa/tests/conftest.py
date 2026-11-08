"""Общие фикстуры (участник 7)."""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.generate_models import PAIRS, build_all


@pytest.fixture(scope="session")
def model_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Папка с сгенерированными моделями. Без pythonocc тесты пропускаются."""
    pytest.importorskip("OCC.Core.gp", reason="pythonocc-core не установлен")
    out = tmp_path_factory.mktemp("models")
    build_all(out)
    return out


@pytest.fixture(scope="session")
def pairs(model_dir: Path) -> dict[str, tuple[Path, Path]]:
    return {p.name: (model_dir / p.file_a, model_dir / p.file_b) for p in PAIRS}
