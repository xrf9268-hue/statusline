# Claude Code Productivity Statusline

A productivity-focused statusline for [Claude Code](https://code.claude.com/docs/en/statusline) that displays coding metrics, performance stats, and development context.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

## Example Output

```
[N] ⏰ 14:30 Sonnet 4.5 statusline:main*2 +1 | $0.125 5m [━━━━──────] 42% 57k/200k | 📝 +127/-43 ↗ | ⚡5.0s
```

| Element | Description |
|---------|-------------|
| `[N]` | Vim mode (N/I/V/R/C) |
| `⏰ 14:30` | Current time |
| `Sonnet 4.5` | Model name (with output style if set) |
| `statusline:main*2 +1` | Directory:branch — 2 dirty files, 1 commit ahead |
| `$0.125 5m [━━━━──────] 42% 57k/200k` | Cost, duration, visual context bar, token usage |
| `📝 +127/-43 ↗` | Lines added/removed with trend arrow |
| `⚡5.0s` | Cumulative API time |

## Features

- **Productivity metrics** — line changes, API time, session cost, duration, trend arrows
- **Visual context bar** — `[━━━━──────] 42% 57k/200k` with green/yellow/red thresholds (CJK-safe Box Drawing glyphs)
- **Git integration** — branch (with smart truncation), dirty count, ahead/behind, detached HEAD
- **Vim mode indicator** — per-mode colors
- **Themes** — `default`, `gruvbox`, `nord`, `minimal`
- **Nerd Font icons** — optional glyph mode
- **Configurable layout** — segment order via env var
- **Zero dependencies** — Python stdlib only

## Installation

```bash
cp statusline-hz.py ~/.claude/
chmod +x ~/.claude/statusline-hz.py
```

Then edit `~/.claude/settings.json`:

```json
{
  "statusLine": {
    "type": "command",
    "command": "~/.claude/statusline-hz.py",
    "padding": 0
  }
}
```

Restart Claude Code. **Requirements:** Python 3.9+, Claude Code v1.2.0+.

## Configuration

All configuration is via environment variables in `settings.json` → `env`.

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `STATUSLINE_LAYOUT` | string | `vim,time,model,dir,cost,lines,api` | Comma-separated segment order |
| `STATUSLINE_THEME` | string | `default` | Palette: `default`, `gruvbox`, `nord`, `minimal` |
| `STATUSLINE_ICON_MODE` | string | `plain` | `plain` (emoji+ASCII) or `nerd_font` (glyphs) |
| `STATUSLINE_CTX_STYLE` | string | `bar` | Context display: `bar` or `text` (legacy `ctx:42%`) |
| `STATUSLINE_GIT_DETAIL` | string | `full` | `full` (count+ahead/behind), `simple` (dot only), `off` |
| `STATUSLINE_BRANCH_MAX_LEN` | int | `25` | Max branch name length; `0` disables truncation |
| `STATUSLINE_COST_THRESHOLD` | float | `0.50` | USD threshold for cost alerts |
| `STATUSLINE_MODEL_ALIASES` | JSON | `{}` | Model id/name → short label, e.g. `{"claude-opus-4-6":"O4.6"}` |
| `STATUSLINE_SHOW_TOKENS` | bool | `0` | Show input/output token counts |
| `STATUSLINE_SHOW_BURNRATE` | bool | `0` | Show per-minute cost rate |
| `STATUSLINE_LOG_LEVEL` | string | `WARNING` | `DEBUG`/`INFO`/`WARNING`/`ERROR`/`CRITICAL`/`OFF` |
| `STATUSLINE_DEBUG` | bool | `0` | Enable debug mode |
| `NO_COLOR` | any | – | Standard: disable all colors (always wins) |

### Layout Segments

| Segment | Description |
|---------|-------------|
| `vim` | Vim mode indicator |
| `time` | Current time |
| `model` | Model name (with output style) |
| `dir` | Directory and git branch |
| `cost` | Cost, duration, and context window |
| `context` | Standalone context (skipped when `cost` present) |
| `tokens` | Token counts (requires `STATUSLINE_SHOW_TOKENS=1`) |
| `lines` | Code change statistics with trend |
| `api` | API performance time |
| `burnrate` | Cost burn rate (requires `STATUSLINE_SHOW_BURNRATE=1`) |

Header segments (`vim`, `time`, `model`, `dir`) join with spaces; the rest are separated by ` | `.

## Visual Reference

### Context Window (3-tier)

| Color | Range | Meaning |
|-------|-------|---------|
| 🟢 Green | < 50% | Plenty remaining |
| 🟡 Yellow | 50–75% | Getting used up |
| 🔴 Red | ≥ 75% | Nearly full |

Each cell of `[━━━━──────]` represents 10% (rounded half-up).

### API Time (cumulative per session)

| Color | Range |
|-------|-------|
| 🟢 Green | < 10s |
| 🟡 Yellow | 10–60s |
| 🔴 Red | > 60s |

### Vim Modes

| Mode | Indicator | Color |
|------|-----------|-------|
| Normal | `[N]` | Green |
| Insert | `[I]` | Yellow |
| Visual | `[V]` | Cyan |
| Replace | `[R]` | Red |
| Command | `[C]` | Dim |

### Git Detail Modes

| Mode | Output |
|------|--------|
| `full` (default) | `main*3 +2 -1` (ASCII) or `main●3 ↑2 ↓1` (nerd_font) |
| `simple` | `main*` |
| `off` | `main` |

### Trend Arrows

`(new)` first session · `↗` >20% more · `→` ±20% similar · `↘` >20% fewer.

## Troubleshooting

| Symptom | Check |
|---------|-------|
| No metrics | Claude Code v1.2.0+, cost tracking enabled, logs in `~/.cache/claude-statusline/logs/` |
| Glyphs misaligned | Switch `STATUSLINE_ICON_MODE=plain` (CJK font width issue) |
| Trends missing | Need ≥2 sessions; cache: `~/.cache/claude-statusline/session_stats.json` (24h TTL) |
| Branch wrong | `STATUSLINE_BRANCH_MAX_LEN=0` to disable truncation |

Invalid env values silently fall back to defaults — the statusline never crashes the host shell.

## Development

```bash
# Run tests
python3 tests/test_statusline.py -v

# Smoke test with mock data
echo '{"workspace":{"current_dir":"."},"model":{"display_name":"Sonnet 4.5"},"cost":{"total_cost_usd":0.125,"total_duration_ms":300000,"total_lines_added":127,"total_lines_removed":43,"total_api_duration_ms":5000}}' | python3 statusline-hz.py

# Debug mode
STATUSLINE_LOG_LEVEL=DEBUG STATUSLINE_DEBUG=1 python3 statusline-hz.py
```

Logs: `~/.cache/claude-statusline/logs/statusline-YYYYMMDD.log`

## License

MIT — see [LICENSE](LICENSE).

---

*Independent project, not affiliated with Anthropic.*
