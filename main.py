#!/usr/bin/env python3
"""WebWork Downloader — Ricardo Passos Advocacia.

Desktop app for batch-downloading daily activity reports from WebWork Tracker.
"""

from ui.app import WebWorkApp


def main():
    app = WebWorkApp()
    app.mainloop()


if __name__ == "__main__":
    main()
