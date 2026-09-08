"""命令行入口 - StudyBuddy 操作员命令。

通过 `python -m app` 或 `python -m backend.app` 启动。
具体命令实现在 cli.py 中。
"""

from .cli import main


if __name__ == "__main__":
    raise SystemExit(main())
