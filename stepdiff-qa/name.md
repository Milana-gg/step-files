
## Все имена, от которых зависят тесты, собраны в `tests/adapters.py` (таблица `API`):

| Что                         | Сейчас в адаптере                        | От кого |
|-----------------------------|------------------------------------------|---------------|
| Имя пакета                  | `stepdiff`                               | участник 1    |
| Сигнатура и поля `compare`  | `compare(ma, ta, mb, tb, tol=...)`, `.match` | участник 1 |
| Загрузка                    | `loader.load_shape(path)`                | участник 4    |
| Исключения при битом файле  | любое `Exception`                        | участник 4    |
| Геометрия                   | `geometry.compute_metrics(shape)`        | участник 6    |
| Топология                   | `topology.analyze_topology(shape)`       | участник 8    |
| JSON-отчёт                  | `report.write_json(result, path)`        | участник 3    |
| График                      | `viz.render_comparison(a, b, result, path)` | участник 5 |
| CLI                         | `python -m stepdiff.cli A B --tol ...`   | участник 2    |
