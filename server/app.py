"""
OpenEnv-compatible server entrypoint.

This small adapter lets the official validator detect a standard
`server.app:main` entrypoint without changing the existing backend app layout.
"""

import uvicorn


def main() -> None:
    uvicorn.run(
        "backend.app.main:app",
        host="0.0.0.0",
        port=7860,
        reload=False,
    )


if __name__ == "__main__":
    main()
