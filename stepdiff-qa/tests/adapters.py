"""Адаптеры к модулям других участников (участник 7).

Тесты вызывают чужой код ТОЛЬКО через этот файл. Пока модуль участника не готов
(нет пакета, нет функции), адаптер печатает заглушку «[Код участника N]» и тест
пропускается (skip), а не падает. Когда модуль появится, тесты включатся сами.

Когда участники договорятся об именах — правится только таблица ниже.
"""
from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

import pytest

# ---- ЕДИНСТВЕННОЕ место, которое надо синхронизировать с остальными ----
PACKAGE = "stepdiff"  # [Код участника 1]: имя пакета из структуры репозитория
LOADER_ERRORS: tuple[type[BaseException], ...] = (Exception,)  # [Код участника 4]: свои исключения
# (модуль, функция, номер участника)
API = {
    "load": ("loader", "load_shape", 4),
    "metrics": ("geometry", "compute_metrics", 6),
    "topology": ("topology", "analyze_topology", 8),
    "compare": ("comparator", "compare", 1),
    "report_json": ("report", "write_json", 3),
    "plot": ("viz", "render_comparison", 5),
}
CLI_MODULE = f"{PACKAGE}.cli"  # [Код участника 2]
# -----------------------------------------------------------------------


def require(key: str) -> Callable[..., Any]:
    """Вернуть функцию чужого модуля или пропустить тест с заглушкой."""
    module, attr, owner = API[key]
    try:
        return getattr(importlib.import_module(f"{PACKAGE}.{module}"), attr)  # type: ignore[no-any-return]
    except (ImportError, AttributeError):
        print(f"[Код участника {owner}]")
        pytest.skip(f"{PACKAGE}.{module}.{attr} ещё не реализован (участник {owner})")


def analyze(path: Path) -> tuple[Any, Any]:
    """Загрузка -> геометрия + топология одной модели."""
    shape = require("load")(path)  # [Код участника 4]
    metrics = require("metrics")(shape)  # [Код участника 6]
    topo = require("topology")(shape)  # [Код участника 8]
    return metrics, topo


def run_pipeline(path_a: Path, path_b: Path, tol: float = 1e-6) -> Any:
    """Вся цепочка: загрузка -> анализ -> сравнение. Возвращает DiffResult."""
    metrics_a, topo_a = analyze(path_a)
    metrics_b, topo_b = analyze(path_b)
    # сигнатуру compare согласовать с участником 1
    return require("compare")(metrics_a, topo_a, metrics_b, topo_b, tol=tol)  # [Код участника 1]


def verdict_is_match(result: Any) -> bool:
    """Вердикт «совпадает» из DiffResult. Имя поля — [Код участника 1]."""
    return bool(getattr(result, "match"))


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    """Запуск CLI как внешнего процесса. Пропуск, если CLI ещё нет."""
    proc = subprocess.run(
        [sys.executable, "-m", CLI_MODULE, *args],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if "No module named" in proc.stderr and CLI_MODULE.split(".")[0] in proc.stderr:
        print("[Код участника 2]")
        pytest.skip("CLI ещё не реализован (участник 2)")
    return proc
