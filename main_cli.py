#!/usr/bin/env python3
import sys
import os
import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

# Добавляем пути, чтобы Python видел локальные файлы и папку src
base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(base_dir)
sys.path.append(os.path.join(base_dir, "src"))

try:
    import module6_geometry
    # Пробуем импортировать компаратор из src/step_compare
    # (пока закомментировано, так как мы не знаем точных имен функций, 
    # но пути для импорта уже настроены)
    # from step_compare.comparator import compare_models 
except ImportError as e:
    console.print(f"[bold red]Ошибка импорта:[/bold red] {e}")
    sys.exit(2)

def call_core_compare(file_a: str, file_b: str, tol: float):
    """
    Здесь будет вызов реальной функции из ядра участника 1.
    Пока мы используем заглушку для проверки работы интерфейса.
    """
    # ВРЕМЕННАЯ ЗАГЛУШКА
    return {
        "match": False,
        "metrics": {
            "volume_a": 150.5, "volume_b": 150.5, "volume_diff": 0.0,
            "area_a": 300.0, "area_b": 300.0, "area_diff": 0.0,
            "faces_a": 12, "faces_b": 12, "faces_diff": 0
        },
        "details": ["Тестовое расхождение (ядро еще не подключено)"]
    }

@click.command()
@click.argument("file_a", type=click.Path(exists=True, readable=True))
@click.argument("file_b", type=click.Path(exists=True, readable=True))
@click.option("--tol", default=1e-6, show_default=True, type=float, help="Допуск.")
@click.option("--plot", is_flag=True, default=False, help="Визуализация.")
@click.option("--report", type=click.Path(dir_okay=False), default=None, help="Сохранить HTML-отчет.")
def compare(file_a, file_b, tol, plot, report):
    """
    Сравнить два CAD-файла: FILE_A и FILE_B.\n
    Коды возврата:\n
      0 — совпали\n
      1 — есть расхождения\n
      2 — ошибка
    """
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("Сравнение моделей...", total=None)
            
            # ВЫЗОВ ЯДРА
            result = call_core_compare(file_a, file_b, tol)
            
            progress.update(task, completed=1)
            
    except Exception as e:
        console.print(f"[bold red]Ошибка:[/bold red] {e}")
        sys.exit(2)

    # --- Вывод таблицы ---
    metrics = result.get("metrics", {})
    table = Table(title="Сравнение моделей")
    table.add_column("Метрика", style="cyan")
    table.add_column("Файл A", justify="right")
    table.add_column("Файл B", justify="right")
    table.add_column("Разница", justify="right")

    rows = [
        ("Объём", "volume_a", "volume_b", "volume_diff"),
        ("Площадь", "area_a", "area_b", "area_diff"),
        ("Грани", "faces_a", "faces_b", "faces_diff"),
    ]
    for label, key_a, key_b, key_diff in rows:
        table.add_row(
            str(label), 
            str(metrics.get(key_a, "—")), 
            str(metrics.get(key_b, "—")), 
            str(metrics.get(key_diff, "—"))
        )
    console.print(table)

    # --- Расхождения ---
    details = result.get("details", [])
    if details:
        console.print("\n[bold yellow]Обнаруженные расхождения:[/bold yellow]")
        for d in details:
            console.print(f"  • {d}")

    # --- Отчет ---
    if report:
        try:
            with open(report, "w", encoding="utf-8") as f:
                f.write(f"<html><body><h1>Сравнение</h1><p>{file_a} vs {file_b}</p></body></html>")
            console.print(f"\n[green]Отчёт сохранён:[/green] {report}")
        except Exception as e:
            console.print(f"[bold red]Не удалось сохранить отчёт:[/bold red] {e}")

    # --- Код возврата ---
    if result.get("match", False):
        console.print("[bold green]Модели совпали.[/bold green]")
        sys.exit(0)
    else:
        console.print("[bold red]Модели имеют расхождения.[/bold red]")
        sys.exit(1)

if __name__ == "__main__":
    compare()