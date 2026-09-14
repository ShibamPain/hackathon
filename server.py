"""Compatibility wrapper: use the integrated app as the single source of truth."""

from app import app


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8000)