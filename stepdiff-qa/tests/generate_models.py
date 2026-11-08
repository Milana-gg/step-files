"""Генератор тестовых пар моделей (участник 7).

Не зависит от кода других участников: использует только pythonocc-core.
Запуск вручную:  python -m tests.generate_models out_dir/

Пары (имя -> ожидаемый результат сравнения):
    identical   box.step  vs box_copy.step       -> match  (код возврата 0)
    shifted     box.step  vs box_shifted.step    -> differ (1) : объём тот же, габариты/центр масс другие
    hole        box.step  vs box_hole.step       -> differ (1) : объём меньше, граней больше
    step_vs_brep box.step vs box.brep            -> match  (0) : формат файла не должен влиять
    damaged     box.step  vs broken.step         -> error  (2) : обрезанный STEP
    empty       box.step  vs empty.step          -> error  (2) : пустой файл

Ожидаемые вердикты согласовать с участником 1 (comparator.py), особенно для shifted.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

BOX_SIZE = (10.0, 20.0, 30.0)  # dx, dy, dz
HOLE_RADIUS = 3.0  # сквозное отверстие вдоль оси Z, по центру
SHIFT_VECTOR = (5.0, 0.0, 0.0)


@dataclass(frozen=True)
class PairSpec:
    name: str
    file_a: str
    file_b: str
    expect: str  # "match" | "differ" | "error"
    description: str


PAIRS: tuple[PairSpec, ...] = (
    PairSpec("identical", "box.step", "box_copy.step", "match", "две одинаковые модели"),
    PairSpec("shifted", "box.step", "box_shifted.step", "differ", "вторая модель сдвинута"),
    PairSpec("hole", "box.step", "box_hole.step", "differ", "во второй есть сквозное отверстие"),
    PairSpec("step_vs_brep", "box.step", "box.brep", "match", "одна и та же форма в разных форматах"),
    PairSpec("damaged", "box.step", "broken.step", "error", "второй файл обрезан"),
    PairSpec("empty", "box.step", "empty.step", "error", "второй файл пустой"),
)


# --- построение форм (OCC импортируется лениво, чтобы модуль грузился без него) ---

def make_box() -> Any:
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox

    return BRepPrimAPI_MakeBox(*BOX_SIZE).Shape()


def make_shifted_box() -> Any:
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCC.Core.gp import gp_Trsf, gp_Vec

    trsf = gp_Trsf()
    trsf.SetTranslation(gp_Vec(*SHIFT_VECTOR))
    return BRepBuilderAPI_Transform(make_box(), trsf, True).Shape()


def make_box_with_hole() -> Any:
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCC.Core.gp import gp_Ax2, gp_Dir, gp_Pnt

    dx, dy, dz = BOX_SIZE
    axis = gp_Ax2(gp_Pnt(dx / 2, dy / 2, -1.0), gp_Dir(0, 0, 1))
    cylinder = BRepPrimAPI_MakeCylinder(axis, HOLE_RADIUS, dz + 2.0).Shape()
    return BRepAlgoAPI_Cut(make_box(), cylinder).Shape()


# --- запись файлов ---

def write_step(shape: Any, path: Path) -> None:
    from OCC.Core.IFSelect import IFSelect_RetDone
    from OCC.Core.STEPControl import STEPControl_AsIs, STEPControl_Writer

    writer = STEPControl_Writer()
    writer.Transfer(shape, STEPControl_AsIs)
    if writer.Write(str(path)) != IFSelect_RetDone:
        raise RuntimeError(f"Не удалось записать STEP: {path}")


def write_brep(shape: Any, path: Path) -> None:
    from OCC.Core import BRepTools

    try:  # новые версии pythonocc
        BRepTools.breptools.Write(shape, str(path))
    except AttributeError:  # старые версии
        BRepTools.breptools_Write(shape, str(path))


def write_damaged(source: Path, target: Path, keep_ratio: float = 0.6) -> None:
    """Обрезаем валидный STEP-файл: структура ломается посреди DATA-секции."""
    text = source.read_text(encoding="utf-8", errors="ignore")
    target.write_text(text[: int(len(text) * keep_ratio)], encoding="utf-8")


def build_all(out_dir: Path) -> dict[str, tuple[Path, Path]]:
    """Создаёт все файлы и возвращает {имя_пары: (путь_a, путь_b)}."""
    out_dir.mkdir(parents=True, exist_ok=True)

    box = make_box()
    write_step(box, out_dir / "box.step")
    write_step(box, out_dir / "box_copy.step")
    write_step(make_shifted_box(), out_dir / "box_shifted.step")
    write_step(make_box_with_hole(), out_dir / "box_hole.step")
    write_brep(box, out_dir / "box.brep")
    write_damaged(out_dir / "box.step", out_dir / "broken.step")
    (out_dir / "empty.step").write_text("", encoding="utf-8")

    return {p.name: (out_dir / p.file_a, out_dir / p.file_b) for p in PAIRS}


def main() -> None:
    parser = argparse.ArgumentParser(description="Сгенерировать тестовые модели")
    parser.add_argument("out_dir", type=Path, help="папка для файлов")
    args = parser.parse_args()
    for name, (a, b) in build_all(args.out_dir).items():
        print(f"{name}: {a.name} <-> {b.name}")


if __name__ == "__main__":
    main()
