import sys

from pos.container import Container
from pos.domain.repositories import StorageError


def main() -> None:
    container = Container()
    if len(sys.argv) > 1:
        container.config.data_dir.from_value(sys.argv[1])
    try:
        console = container.console()
    except StorageError as error:
        print(f"Не удалось открыть данные: {error}")
        raise SystemExit(1) from None
    try:
        console.run()
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    main()
