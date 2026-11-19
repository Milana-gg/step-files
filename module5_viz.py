#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
module5_viz.py — модуль визуализации для инструмента геометрического
сравнения двух версий STEP/BREP-файлов (PythonOCC + matplotlib).

Возможности:
  * триангуляция моделей через BRepMesh_IncrementalMesh;
  * 3D-отрисовка двух моделей в mpl_toolkits.mplot3d: рядом (side) или наложением (overlay);
  * раскраска моделей и подсветка различающихся граней;
  * столбчатая диаграмма метрик A и B (small multiples);
  * радар процентных отклонений B относительно A;
  * единая палитра и легенда, сохранение каждого графика в PNG и SVG.

Пример:
  python module5_viz.py v1.step v2.step -o report --mode both
"""
from __future__ import annotations

import argparse
import importlib
import math
import os
import sys
from dataclasses import dataclass

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import to_rgb
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from mpl_toolkits.mplot3d.art3d import Poly3DCollection  # noqa: F401  (регистрирует 3d-проекцию)

from OCC.Core.BRep import BRep_Builder, BRep_Tool
from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
from OCC.Core.Bnd import Bnd_Box
from OCC.Core.GProp import GProp_GProps
from OCC.Core.IFSelect import IFSelect_RetDone
from OCC.Core.STEPControl import STEPControl_Reader
from OCC.Core.TopAbs import (TopAbs_EDGE, TopAbs_FACE, TopAbs_REVERSED,
                             TopAbs_SOLID, TopAbs_VERTEX)
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopLoc import TopLoc_Location
from OCC.Core.TopoDS import TopoDS_Shape
from OCC.Core.TopTools import TopTools_IndexedMapOfShape


# ════════════════════════════════════════════════════════════════════════════
#  Совместимость с разными версиями pythonocc-core (7.4 … 7.8+)
# ════════════════════════════════════════════════════════════════════════════
def _occ_fn(module: str, cls: str, name: str):
    """Возвращает cls.name (новый API) или cls_name (старый API)."""
    mod = importlib.import_module(f"OCC.Core.{module}")
    holder = getattr(mod, cls, None)
    if holder is not None and hasattr(holder, name):
        return getattr(holder, name)
    return getattr(mod, f"{cls}_{name}")


_volume_props = _occ_fn("BRepGProp", "brepgprop", "VolumeProperties")
_surface_props = _occ_fn("BRepGProp", "brepgprop", "SurfaceProperties")
_bnd_add = _occ_fn("BRepBndLib", "brepbndlib", "Add")
_brep_read = _occ_fn("BRepTools", "breptools", "Read")
_to_face = _occ_fn("TopoDS", "topods", "Face")
_map_shapes = _occ_fn("TopExp", "topexp", "MapShapes")


# ════════════════════════════════════════════════════════════════════════════
#  Единая палитра и стиль
# ════════════════════════════════════════════════════════════════════════════
PALETTE = {
    "A": "#4C78A8",         # модель A — синий
    "B": "#F58518",         # модель B — оранжевый
    "only_a": "#E45756",    # грани, отличающиеся в A (удалено/изменено) — красный
    "only_b": "#54A24B",    # грани, отличающиеся в B (добавлено/изменено) — зелёный
    "common": "#BAB0AC",    # совпадающие грани (режим наложения) — серый
    "neutral": "#6E6E6E",
    "grid": "#DDDDDD",
    "text": "#222222",
}

LIGHT_DIR = np.array([0.35, -0.55, 0.75])
LIGHT_DIR = LIGHT_DIR / np.linalg.norm(LIGHT_DIR)

plt.rcParams.update({
    "font.family": "DejaVu Sans",      # поддерживает кириллицу
    "font.size": 10,
    "axes.titlesize": 11,
    "axes.titleweight": "bold",
    "axes.edgecolor": PALETTE["neutral"],
    "axes.labelcolor": PALETTE["text"],
    "axes.grid": True,
    "grid.color": PALETTE["grid"],
    "grid.linewidth": 0.6,
    "xtick.color": PALETTE["text"],
    "ytick.color": PALETTE["text"],
    "figure.facecolor": "white",
    "savefig.facecolor": "white",
    "svg.fonttype": "none",            # текст в SVG остаётся редактируемым
})


# ════════════════════════════════════════════════════════════════════════════
#  Структуры данных
# ════════════════════════════════════════════════════════════════════════════
@dataclass
class FaceMesh:
    index: int
    verts: np.ndarray      # (n, 3)
    tris: np.ndarray       # (m, 3) индексы вершин
    area: float
    centroid: np.ndarray   # (3,)
    stype: int             # GeomAbs_SurfaceType


@dataclass
class ModelData:
    name: str
    shape: TopoDS_Shape
    faces: list[FaceMesh]
    bbox: tuple[float, float, float, float, float, float]
    metrics: dict[str, float]
    center_of_mass: np.ndarray


# ════════════════════════════════════════════════════════════════════════════
#  Загрузка и метрики
# ════════════════════════════════════════════════════════════════════════════
def load_shape(path: str) -> TopoDS_Shape:
    ext = os.path.splitext(path)[1].lower()
    if ext in (".step", ".stp"):
        reader = STEPControl_Reader()
        if reader.ReadFile(path) != IFSelect_RetDone:
            raise RuntimeError(f"Не удалось прочитать STEP: {path}")
        reader.TransferRoots()
        shape = reader.OneShape()
    elif ext in (".brep", ".brp"):
        shape = TopoDS_Shape()
        if not _brep_read(shape, path, BRep_Builder()):
            raise RuntimeError(f"Не удалось прочитать BREP: {path}")
    else:
        raise ValueError(f"Неподдерживаемый формат: {ext}")
    if shape is None or shape.IsNull():
        raise RuntimeError(f"Пустая геометрия: {path}")
    return shape


def bounding_box(shape: TopoDS_Shape) -> tuple[float, ...]:
    box = Bnd_Box()
    _bnd_add(shape, box, False)
    return box.Get()  # xmin, ymin, zmin, xmax, ymax, zmax


def _count(shape: TopoDS_Shape, kind) -> int:
    m = TopTools_IndexedMapOfShape()
    _map_shapes(shape, kind, m)
    return m.Size()


def compute_metrics(shape: TopoDS_Shape, bbox) -> tuple[dict[str, float], np.ndarray]:
    vprops = GProp_GProps()
    _volume_props(shape, vprops)
    sprops = GProp_GProps()
    _surface_props(shape, sprops)
    com = vprops.CentreOfMass()
    xmin, ymin, zmin, xmax, ymax, zmax = bbox
    metrics = {
        "Объём": abs(vprops.Mass()),
        "Площадь поверхности": sprops.Mass(),
        "Габарит X": xmax - xmin,
        "Габарит Y": ymax - ymin,
        "Габарит Z": zmax - zmin,
        "Тела": float(_count(shape, TopAbs_SOLID)),
        "Грани": float(_count(shape, TopAbs_FACE)),
        "Рёбра": float(_count(shape, TopAbs_EDGE)),
        "Вершины": float(_count(shape, TopAbs_VERTEX)),
    }
    return metrics, np.array([com.X(), com.Y(), com.Z()])


INTEGER_METRICS = {"Тела", "Грани", "Рёбра", "Вершины"}


# ════════════════════════════════════════════════════════════════════════════
#  Триангуляция
# ════════════════════════════════════════════════════════════════════════════
def _triangulation_arrays(tri, loc: TopLoc_Location, reversed_face: bool):
    n_nodes = tri.NbNodes()
    trsf = None if loc.IsIdentity() else loc.Transformation()
    nodes_arr = None if hasattr(tri, "Node") else tri.Nodes()

    verts = np.empty((n_nodes, 3), dtype=float)
    for i in range(1, n_nodes + 1):
        p = tri.Node(i) if nodes_arr is None else nodes_arr.Value(i)
        if trsf is not None:
            p = p.Transformed(trsf)
        verts[i - 1] = (p.X(), p.Y(), p.Z())

    n_tris = tri.NbTriangles()
    tris_arr = None if hasattr(tri, "Triangle") else tri.Triangles()
    tris = np.empty((n_tris, 3), dtype=np.int64)
    for i in range(1, n_tris + 1):
        t = tri.Triangle(i) if tris_arr is None else tris_arr.Value(i)
        a, b, c = t.Get()
        tris[i - 1] = (a - 1, c - 1, b - 1) if reversed_face else (a - 1, b - 1, c - 1)
    return verts, tris


def triangulate(shape: TopoDS_Shape, linear_deflection: float,
                angular_deflection: float = 0.5) -> list[FaceMesh]:
    """Триангулирует модель и возвращает сетку для каждой грани."""
    mesher = BRepMesh_IncrementalMesh(shape, linear_deflection, False,
                                      angular_deflection, True)
    mesher.Perform()

    faces: list[FaceMesh] = []
    exp = TopExp_Explorer(shape, TopAbs_FACE)
    idx = 0
    while exp.More():
        face = _to_face(exp.Current())
        loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation(face, loc)
        if tri is not None and not (hasattr(tri, "IsNull") and tri.IsNull()):
            verts, tris = _triangulation_arrays(
                tri, loc, face.Orientation() == TopAbs_REVERSED)
            props = GProp_GProps()
            _surface_props(face, props)
            c = props.CentreOfMass()
            faces.append(FaceMesh(
                index=idx, verts=verts, tris=tris, area=props.Mass(),
                centroid=np.array([c.X(), c.Y(), c.Z()]),
                stype=int(BRepAdaptor_Surface(face).GetType()),
            ))
        idx += 1
        exp.Next()
    return faces


def build_model(path: str, linear_deflection: float | None,
                angular_deflection: float, rel_deflection: float) -> ModelData:
    shape = load_shape(path)
    bbox = bounding_box(shape)
    diag = math.dist(bbox[:3], bbox[3:]) or 1.0
    lin = linear_deflection if linear_deflection else diag * rel_deflection
    faces = triangulate(shape, lin, angular_deflection)
    metrics, com = compute_metrics(shape, bbox)
    return ModelData(os.path.basename(path), shape, faces, bbox, metrics, com)


# ════════════════════════════════════════════════════════════════════════════
#  Поиск различающихся граней
# ════════════════════════════════════════════════════════════════════════════
def diff_faces(fa: list[FaceMesh], fb: list[FaceMesh], diag: float,
               rel_tol: float = 1e-3) -> tuple[set[int], set[int]]:
    """
    Жадное сопоставление граней по (тип поверхности, площадь, центр масс).
    Возвращает индексы граней A и B, для которых пара не найдена.
    """
    if not fb:
        return {f.index for f in fa}, set()
    b_cent = np.array([g.centroid for g in fb])
    b_area = np.array([g.area for g in fb])
    b_type = np.array([g.stype for g in fb])
    free = np.ones(len(fb), dtype=bool)
    pos_tol = rel_tol * diag

    unmatched_a: set[int] = set()
    for f in fa:
        area_tol = rel_tol * max(f.area, 1e-12) + 1e-9
        dist = np.linalg.norm(b_cent - f.centroid, axis=1)
        ok = free & (b_type == f.stype) & (np.abs(b_area - f.area) <= area_tol) & (dist <= pos_tol)
        if ok.any():
            cand = np.where(ok)[0]
            free[cand[np.argmin(dist[cand])]] = False
        else:
            unmatched_a.add(f.index)
    unmatched_b = {fb[i].index for i in np.where(free)[0]}
    return unmatched_a, unmatched_b


# ════════════════════════════════════════════════════════════════════════════
#  3D-визуализация
# ════════════════════════════════════════════════════════════════════════════
def _face_polys(faces: list[FaceMesh], color_of, alpha_of):
    polys, colors = [], []
    for f in faces:
        if len(f.tris) == 0:
            continue
        pts = f.verts[f.tris]                                   # (m, 3, 3)
        n = np.cross(pts[:, 1] - pts[:, 0], pts[:, 2] - pts[:, 0])
        n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-15
        shade = 0.45 + 0.55 * np.abs(n @ LIGHT_DIR)             # ламбертово освещение
        rgb = np.clip(np.outer(shade, to_rgb(color_of(f))), 0, 1)
        rgba = np.column_stack([rgb, np.full(len(rgb), alpha_of(f))])
        polys.append(pts)
        colors.append(rgba)
    if not polys:
        return None, None
    return np.concatenate(polys), np.concatenate(colors)


def _add_mesh(ax, faces, color_of, alpha_of, edge_lw=0.0):
    polys, colors = _face_polys(faces, color_of, alpha_of)
    if polys is None:
        return
    coll = Poly3DCollection(polys, facecolors=colors, linewidths=edge_lw,
                            edgecolors=(0, 0, 0, 0.08) if edge_lw else None)
    ax.add_collection3d(coll)


def _setup_axes(ax, bbox, title, elev=25, azim=-60):
    lo = np.array(bbox[:3])
    hi = np.array(bbox[3:])
    center = (lo + hi) / 2
    half = max((hi - lo).max() / 2, 1e-6) * 1.05
    ax.set_xlim(center[0] - half, center[0] + half)
    ax.set_ylim(center[1] - half, center[1] + half)
    ax.set_zlim(center[2] - half, center[2] + half)
    ax.set_box_aspect((1, 1, 1))
    ax.view_init(elev=elev, azim=azim)
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")
    for pane in (ax.xaxis.pane, ax.yaxis.pane, ax.zaxis.pane):
        pane.set_facecolor((0.97, 0.97, 0.97, 1.0))
        pane.set_edgecolor(PALETTE["grid"])
    ax.set_title(title, color=PALETTE["text"])


def _union_bbox(b1, b2):
    return (min(b1[0], b2[0]), min(b1[1], b2[1]), min(b1[2], b2[2]),
            max(b1[3], b2[3]), max(b1[4], b2[4]), max(b1[5], b2[5]))


def plot_models_side(ma: ModelData, mb: ModelData, da: set[int], db: set[int],
                     elev=25, azim=-60):
    """Две модели рядом, отличающиеся грани подсвечены."""
    bbox = _union_bbox(ma.bbox, mb.bbox)
    fig = plt.figure(figsize=(14, 7))
    ax1 = fig.add_subplot(1, 2, 1, projection="3d")
    ax2 = fig.add_subplot(1, 2, 2, projection="3d")

    _add_mesh(ax1, ma.faces,
              lambda f: PALETTE["only_a"] if f.index in da else PALETTE["A"],
              lambda f: 1.0, edge_lw=0.1)
    _add_mesh(ax2, mb.faces,
              lambda f: PALETTE["only_b"] if f.index in db else PALETTE["B"],
              lambda f: 1.0, edge_lw=0.1)

    _setup_axes(ax1, bbox, f"A: {ma.name}\nотличается граней: {len(da)} из {len(ma.faces)}", elev, azim)
    _setup_axes(ax2, bbox, f"B: {mb.name}\nотличается граней: {len(db)} из {len(mb.faces)}", elev, azim)

    handles = [
        Patch(color=PALETTE["A"], label="Модель A"),
        Patch(color=PALETTE["B"], label="Модель B"),
        Patch(color=PALETTE["only_a"], label="Отличается в A (удалено / изменено)"),
        Patch(color=PALETTE["only_b"], label="Отличается в B (добавлено / изменено)"),
    ]
    fig.legend(handles=handles, loc="lower center", ncol=4, frameon=False)
    fig.suptitle("Геометрическое сравнение моделей — рядом", fontsize=14, fontweight="bold")
    fig.subplots_adjust(left=0.02, right=0.98, top=0.86, bottom=0.08, wspace=0.05)
    return fig


def plot_models_overlay(ma: ModelData, mb: ModelData, da: set[int], db: set[int],
                        elev=25, azim=-60):
    """Наложение моделей: общие грани полупрозрачно, различия — насыщенным цветом."""
    bbox = _union_bbox(ma.bbox, mb.bbox)
    fig = plt.figure(figsize=(10, 9))
    ax = fig.add_subplot(1, 1, 1, projection="3d")

    # общие грани рисуем один раз (по модели B)
    common_b = [f for f in mb.faces if f.index not in db]
    _add_mesh(ax, common_b, lambda f: PALETTE["common"], lambda f: 0.25)
    _add_mesh(ax, [f for f in ma.faces if f.index in da],
              lambda f: PALETTE["only_a"], lambda f: 0.85, edge_lw=0.1)
    _add_mesh(ax, [f for f in mb.faces if f.index in db],
              lambda f: PALETTE["only_b"], lambda f: 0.85, edge_lw=0.1)

    _setup_axes(ax, bbox, f"A: {ma.name}   ⟷   B: {mb.name}", elev, azim)
    handles = [
        Patch(color=PALETTE["common"], alpha=0.5, label="Совпадающие грани"),
        Patch(color=PALETTE["only_a"], label=f"Только в A ({len(da)})"),
        Patch(color=PALETTE["only_b"], label=f"Только в B ({len(db)})"),
    ]
    fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False)
    fig.suptitle("Геометрическое сравнение моделей — наложение", fontsize=14, fontweight="bold")
    fig.subplots_adjust(left=0.02, right=0.98, top=0.9, bottom=0.07)
    return fig


# ════════════════════════════════════════════════════════════════════════════
#  Графики метрик
# ════════════════════════════════════════════════════════════════════════════
def pct_deviation(a: float, b: float) -> float:
    if abs(a) < 1e-12:
        return 0.0 if abs(b) < 1e-12 else math.copysign(100.0, b)
    return (b - a) / abs(a) * 100.0


def _fmt(key: str, v: float) -> str:
    return f"{int(round(v))}" if key in INTEGER_METRICS else f"{v:.4g}"


def _dev_color(d: float) -> str:
    if abs(d) < 1e-9:
        return PALETTE["neutral"]
    return PALETTE["only_b"] if d > 0 else PALETTE["only_a"]


def plot_metrics_bar(ma: ModelData, mb: ModelData, ncols: int = 3):
    """Столбчатые диаграммы метрик A и B (отдельная панель на метрику)."""
    keys = list(ma.metrics)
    nrows = math.ceil(len(keys) / ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(4.2 * ncols, 3.2 * nrows))
    axes = np.atleast_1d(axes).ravel()

    for ax, key in zip(axes, keys):
        a, b = ma.metrics[key], mb.metrics.get(key, 0.0)
        bars = ax.bar([0, 1], [a, b], width=0.6,
                      color=[PALETTE["A"], PALETTE["B"]], edgecolor="white", zorder=3)
        ax.set_xticks([0, 1])
        ax.set_xticklabels(["A", "B"])
        ax.set_title(key)
        ax.grid(axis="x", visible=False)
        top = max(a, b)
        ax.set_ylim(0, top * 1.3 if top > 0 else 1)
        for bar, v in zip(bars, (a, b)):
            ax.annotate(_fmt(key, v), (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                        xytext=(0, 3), textcoords="offset points",
                        ha="center", va="bottom", fontsize=9, color=PALETTE["text"])
        d = pct_deviation(a, b)
        ax.text(0.5, 0.93, f"Δ {d:+.2f}%", transform=ax.transAxes, ha="center",
                va="top", fontsize=10, fontweight="bold", color=_dev_color(d))
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)

    for ax in axes[len(keys):]:
        ax.axis("off")

    handles = [Patch(color=PALETTE["A"], label=f"A: {ma.name}"),
               Patch(color=PALETTE["B"], label=f"B: {mb.name}")]
    fig.legend(handles=handles, loc="lower center", ncol=2, frameon=False)
    fig.suptitle("Метрики моделей A и B", fontsize=14, fontweight="bold")
    fig.tight_layout(rect=(0, 0.05, 1, 0.95))
    return fig


def plot_deviation_radar(ma: ModelData, mb: ModelData):
    """Радар процентных отклонений B относительно A (со знаком, кольцо 0% выделено)."""
    keys = list(ma.metrics)
    vals = np.array([pct_deviation(ma.metrics[k], mb.metrics.get(k, 0.0)) for k in keys])
    n = len(keys)
    ang = np.linspace(0, 2 * np.pi, n, endpoint=False)
    ang_c = np.append(ang, ang[0])
    vals_c = np.append(vals, vals[0])
    lim = max(5.0, float(np.abs(vals).max()) * 1.25)

    fig = plt.figure(figsize=(8, 8))
    ax = fig.add_subplot(111, polar=True)
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_ylim(-lim, lim)

    ring = np.linspace(0, 2 * np.pi, 256)
    ax.plot(ring, np.zeros_like(ring), color=PALETTE["neutral"], lw=1.2, ls="--", zorder=2)
    ax.plot(ang_c, vals_c, color=PALETTE["B"], lw=2, zorder=3)
    ax.fill(ang_c, vals_c, color=PALETTE["B"], alpha=0.18, zorder=2)
    ax.scatter(ang, vals, s=45, zorder=4, c=[_dev_color(v) for v in vals],
               edgecolors="white", linewidths=0.8)

    for a, v in zip(ang, vals):
        ax.text(a, v + lim * 0.1 * (1 if v >= 0 else -1), f"{v:+.2f}%",
                ha="center", va="center", fontsize=9, fontweight="bold", color=_dev_color(v))

    ax.set_xticks(ang)
    ax.set_xticklabels(keys, fontsize=10)
    ax.tick_params(axis="y", labelsize=8, colors=PALETTE["neutral"])
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda y, _: f"{y:+.0f}%"))
    ax.grid(color=PALETTE["grid"])

    handles = [
        Line2D([0], [0], color=PALETTE["B"], lw=2, label="Отклонение B от A, %"),
        Line2D([0], [0], color=PALETTE["neutral"], lw=1.2, ls="--", label="0% — без изменений"),
        Line2D([0], [0], marker="o", ls="", color=PALETTE["only_b"], label="Рост"),
        Line2D([0], [0], marker="o", ls="", color=PALETTE["only_a"], label="Уменьшение"),
    ]
    fig.legend(handles=handles, loc="lower center", ncol=2, frameon=False)
    fig.suptitle(f"Радар отклонений: {mb.name} относительно {ma.name}",
                 fontsize=13, fontweight="bold")
    fig.subplots_adjust(top=0.88, bottom=0.13)
    return fig


# ════════════════════════════════════════════════════════════════════════════
#  Сохранение
# ════════════════════════════════════════════════════════════════════════════
def save_figure(fig, out_dir: str, name: str, dpi: int = 200) -> list[str]:
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for ext in ("png", "svg"):
        p = os.path.join(out_dir, f"{name}.{ext}")
        fig.savefig(p, dpi=dpi if ext == "png" else None, bbox_inches="tight")
        paths.append(p)
    plt.close(fig)
    return paths


# ════════════════════════════════════════════════════════════════════════════
#  Публичный API
# ════════════════════════════════════════════════════════════════════════════
def visualize(path_a: str, path_b: str, out_dir: str = "report", mode: str = "both",
              linear_deflection: float | None = None, rel_deflection: float = 1e-3,
              angular_deflection: float = 0.5, tol: float = 1e-3,
              elev: float = 25, azim: float = -60, dpi: int = 200) -> dict:
    ma = build_model(path_a, linear_deflection, angular_deflection, rel_deflection)
    mb = build_model(path_b, linear_deflection, angular_deflection, rel_deflection)

    ub = _union_bbox(ma.bbox, mb.bbox)
    diag = math.dist(ub[:3], ub[3:]) or 1.0
    da, db = diff_faces(ma.faces, mb.faces, diag, tol)

    saved: list[str] = []
    if mode in ("side", "both"):
        saved += save_figure(plot_models_side(ma, mb, da, db, elev, azim), out_dir, "models_side", dpi)
    if mode in ("overlay", "both"):
        saved += save_figure(plot_models_overlay(ma, mb, da, db, elev, azim), out_dir, "models_overlay", dpi)
    saved += save_figure(plot_metrics_bar(ma, mb), out_dir, "metrics_bar", dpi)
    saved += save_figure(plot_deviation_radar(ma, mb), out_dir, "deviation_radar", dpi)

    return {
        "model_a": ma, "model_b": mb,
        "diff_faces_a": sorted(da), "diff_faces_b": sorted(db),
        "com_shift": float(np.linalg.norm(mb.center_of_mass - ma.center_of_mass)),
        "files": saved,
    }


def _print_summary(res: dict) -> None:
    ma, mb = res["model_a"], res["model_b"]
    w = max(len(k) for k in ma.metrics)
    print(f"\n{'Метрика':<{w}}  {'A':>14}  {'B':>14}  {'Δ, %':>9}")
    print("─" * (w + 43))
    for k, a in ma.metrics.items():
        b = mb.metrics.get(k, 0.0)
        print(f"{k:<{w}}  {_fmt(k, a):>14}  {_fmt(k, b):>14}  {pct_deviation(a, b):>+9.2f}")
    print("─" * (w + 43))
    print(f"Смещение центра масс: {res['com_shift']:.6g}")
    print(f"Отличающихся граней: A — {len(res['diff_faces_a'])}, B — {len(res['diff_faces_b'])}")
    print("\nСохранено:")
    for p in res["files"]:
        print("  ", p)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Визуализация геометрического сравнения двух STEP/BREP-файлов")
    ap.add_argument("file_a", help="исходная версия (A): .step/.stp/.brep")
    ap.add_argument("file_b", help="новая версия (B): .step/.stp/.brep")
    ap.add_argument("-o", "--out", default="report", help="папка для PNG/SVG (по умолчанию report)")
    ap.add_argument("--mode", choices=("side", "overlay", "both"), default="both",
                    help="режим 3D-отображения моделей")
    ap.add_argument("--lin", type=float, default=None,
                    help="абсолютный линейный прогиб сетки (по умолчанию — от диагонали габарита)")
    ap.add_argument("--rel-lin", type=float, default=1e-3,
                    help="линейный прогиб как доля диагонали габарита")
    ap.add_argument("--ang", type=float, default=0.5, help="угловой прогиб, рад")
    ap.add_argument("--tol", type=float, default=1e-3,
                    help="относительный допуск сопоставления граней")
    ap.add_argument("--elev", type=float, default=25, help="угол возвышения камеры")
    ap.add_argument("--azim", type=float, default=-60, help="азимут камеры")
    ap.add_argument("--dpi", type=int, default=200, help="разрешение PNG")
    args = ap.parse_args(argv)

    for p in (args.file_a, args.file_b):
        if not os.path.isfile(p):
            print(f"Файл не найден: {p}", file=sys.stderr)
            return 2
    try:
        res = visualize(args.file_a, args.file_b, args.out, args.mode,
                        args.lin, args.rel_lin, args.ang, args.tol,
                        args.elev, args.azim, args.dpi)
    except Exception as exc:  # noqa: BLE001
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1
    _print_summary(res)
    return 0


if __name__ == "__main__":
    sys.exit(main())
