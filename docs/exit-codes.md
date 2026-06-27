# Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Clean run — no findings or no threshold exceeded |
| 1 | Findings at or above `--threshold` (CI mode) |
| 2 | CRITICAL severity findings present |
| 128 + N | Process terminated by signal N (e.g. 130 = SIGINT, 143 = SIGTERM) |
