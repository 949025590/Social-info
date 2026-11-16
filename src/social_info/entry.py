import sys

from social_info.runtime import configure_runtime


def main():
    configure_runtime()
    if len(sys.argv) == 1:
        from social_info.tray import main as tray_main
        tray_main()
    else:
        from social_info.server import main as server_main
        server_main()


if __name__ == "__main__":
    main()
