# Claude Code Productivity Statusline

A productivity-focused statusline for [Claude Code](https://code.claude.com/docs/en/statusline) that displays coding metrics, performance statistics, and development context.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.7+](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)

## Overview

This statusline transforms Claude Code's status bar into a developer productivity dashboard, showing real-time metrics that matter for coding: code changes, API performance, cost tracking, and git status.

## Quick Start

```bash
# 1. Copy the script
cp statusline-hz.py ~/.claude/

# 2. Make it executable
chmod +x ~/.claude/statusline-hz.py

# 3. Configure Claude Code (see Configuration section)

# 4. Restart Claude Code
```

## Example Output

```
[N] ⏰ 14:30 Sonnet 4.5 statusline:main●2↑1 | [$0.125 5m [████░░░░░░] 42% 57k/200k] | 📝 +127/-43 ↗ | ⚡5.0s
```

**Output Breakdown:**

| Element | Description |
|---------|-------------|
| `[N]` | Vim mode indicator (N=Normal, I=Insert, V=Visual, R=Replace) |
| `⏰ 14:30` | Current time |
| `Sonnet 4.5` | AI model name (color: orange), with output style if set |
| `statusline:main●2↑1` | Directory:branch with 2 uncommitted files, 1 ahead of upstream |
| `[$0.125 5m [████░░░░░░] 42% 57k/200k]` | Session cost, duration, visual context window bar with token usage |
| `📝 +127/-43 ↗` | Lines added/removed with trend arrow (color: green) |
| `⚡5.0s` | Cumulative API time (color-coded by session length) |

## Features

### Core Metrics

- **Code Change Statistics** - Real-time tracking of lines added/removed
- **API Performance Monitoring** - Response time with color-coded indicators
- **Cost Tracking** - Session cost with configurable threshold alerts
- **Session Duration** - Time spent in current session (shows seconds if < 1 minute)
- **Git Status** - Branch name with uncommitted changes indicator

### Advanced Features

- **Vim Mode Indicator** - Shows current vim mode `[N]`/`[I]`/`[V]`/`[R]`/`[C]` with per-mode colors
- **Visual Context Window Bar** - ASCII progress bar `[████░░░░░░] 42% 57k/200k` with 3-level color thresholds (green/yellow/red); legacy `ctx:42%` text mode also available
- **Git Detail** - Uncommitted file count + upstream ahead/behind indicators (`main●3↑2↓1`)
- **Theme System** - Built-in palettes: `default`, `gruvbox`, `nord`, `minimal` (env switch)
- **Nerd Font Icons** - Optional Nerd Font glyph mode in addition to plain emoji icons
- **Custom Model Aliases** - Map model id/display name to a short label via JSON env var
- **Token Count Display** - Optional `tok:45.0K/12.0K` input/output token counts
- **Cost Burn Rate** - Optional per-minute cost rate `(0.05/m)`
- **Output Style Display** - Shows active output style next to model name
- **200K+ Token Warning** - Alert when session exceeds 200K tokens
- **Configurable Layout** - Customize segment order via `STATUSLINE_LAYOUT` environment variable
- **Trend Analysis** - Compare current session with previous (`↗` increased, `→` similar, `↘` decreased, `(new)` first session)
- **Cost Alerts** - Warning emoji `⚠️` when cost exceeds threshold
- **Smart Color Coding** - Visual hierarchy for quick information parsing
- **Cross-platform Support** - Works on macOS, Linux, and Windows (fcntl/msvcrt file locking)
- **Graceful Degradation** - Works even without git or with invalid configuration
- **Detached HEAD Support** - Shows short commit hash with `@` prefix when not on a branch
- **Git Status Caching** - 5-second cache for performance optimization
- **File Locking** - Safe concurrent access for multi-instance usage

## Requirements

- **Python**: 3.7 or higher
- **Claude Code**: Latest version (tested on v1.2.0+)
- **Git** (optional): For branch and dirty status display
- **Dependencies**: Standard library only (no external packages required)

## Installation

### Step 1: Copy Script

```bash
cp statusline-hz.py ~/.claude/
chmod +x ~/.claude/statusline-hz.py
```

### Step 2: Configure Claude Code

Edit your `.claude/settings.json`:

```json
{
  "statusLine": {
    "type": "command",
    "command": "~/.claude/statusline-hz.py",
    "padding": 0
  },
  "env": {
    "STATUSLINE_COST_THRESHOLD": "0.50",
    "STATUSLINE_LOG_LEVEL": "WARNING",
    "STATUSLINE_DEBUG": "0",
    "STATUSLINE_SHOW_TOKENS": "0",
    "STATUSLINE_SHOW_BURNRATE": "0",
    "STATUSLINE_LAYOUT": "vim,time,model,dir,cost,lines,api"
  }
}
```

### Step 3: Restart Claude Code

The statusline will appear at the bottom of your Claude Code interface.

## Configuration

### Environment Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `STATUSLINE_COST_THRESHOLD` | float | `0.50` | USD threshold for cost alerts |
| `STATUSLINE_LOG_LEVEL` | string | `WARNING` | Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL, OFF) |
| `STATUSLINE_DEBUG` | boolean | `0` | Enable debug mode (0 or 1) |
| `STATUSLINE_SHOW_TOKENS` | boolean | `0` | Show input/output token counts |
| `STATUSLINE_SHOW_BURNRATE` | boolean | `0` | Show cost burn rate per minute |
| `STATUSLINE_LAYOUT` | string | `vim,time,model,dir,cost,lines,api` | Comma-separated segment order |
| `STATUSLINE_THEME` | string | `default` | Color palette: `default`, `gruvbox`, `nord`, `minimal` |
| `STATUSLINE_ICON_MODE` | string | `plain` | Icon set: `plain` (emoji) or `nerd_font` (Nerd Font glyphs) |
| `STATUSLINE_CTX_STYLE` | string | `bar` | Context window style: `bar` (visual) or `text` (legacy `ctx:42%`) |
| `STATUSLINE_GIT_DETAIL` | string | `full` | Git indicator: `full` (count+ahead/behind), `simple` (dot only), `off` |
| `STATUSLINE_MODEL_ALIASES` | JSON | `{}` | Model id/name → display alias, e.g. `{"claude-opus-4-6":"O4.6"}` |
| `NO_COLOR` | any | - | Disable color output (standard) |

### Layout System

The `STATUSLINE_LAYOUT` environment variable controls which segments appear and in what order. Available segments:

| Segment | Description |
|---------|-------------|
| `vim` | Vim mode indicator |
| `time` | Current time |
| `model` | Model name (with output style) |
| `dir` | Directory and git branch |
| `cost` | Cost, duration, and context window |
| `context` | Standalone context window (skipped when `cost` is in layout) |
| `tokens` | Token counts (requires `STATUSLINE_SHOW_TOKENS=1`) |
| `lines` | Code change statistics with trend |
| `api` | API performance time |
| `burnrate` | Cost burn rate (requires `STATUSLINE_SHOW_BURNRATE=1`) |

Header segments (`vim`, `time`, `model`, `dir`) are joined with spaces. All other segments are separated by ` | `.

### Performance Indicators

#### Context Window Usage Colors

| Color | Range | Meaning |
|-------|-------|---------|
| 🟢 Green | < 50% | Plenty of context remaining |
| 🟡 Yellow | 50% - 75% | Context getting used up |
| 🔴 Red | ≥ 75% | Context nearly full |

The default visual bar `[████░░░░░░] 42% 57k/200k` uses three glyphs per cell:
`█` (filled, ≥80% of cell), `▄` (half, ≥30% of cell), `░` (empty). Set
`STATUSLINE_CTX_STYLE=text` to fall back to the legacy `ctx:42%` format.

#### Themes

Switch with `STATUSLINE_THEME=<name>`:

| Theme | Style |
|-------|-------|
| `default` | Eye-friendly muted palette (current) |
| `gruvbox` | Warm retro |
| `nord` | Cool arctic |
| `minimal` | Mostly grayscale, only red for alerts |

`NO_COLOR=1` always wins and disables all colors.

#### Git Detail Modes

`STATUSLINE_GIT_DETAIL`:

| Mode | Output |
|------|--------|
| `full` (default) | `main●3↑2↓1` — file count, commits ahead, commits behind |
| `simple` | `main●` — single dirty dot only |
| `off` | `main` — no indicators |

#### Cumulative API Time Colors

The API time shown is the **cumulative** time spent on API calls during the session:

| Color | Range | Meaning |
|-------|-------|---------|
| 🟢 Green | < 10s | Fast session, minimal API usage |
| 🟡 Yellow | 10s - 60s | Normal session, moderate API usage |
| 🔴 Red | > 60s | Long session, significant API usage |

#### Vim Mode Colors

| Mode | Indicator | Color |
|------|-----------|-------|
| Normal | `[N]` | 🟢 Green |
| Insert | `[I]` | 🟡 Yellow |
| Visual | `[V]` | 🔵 Cyan |
| Replace | `[R]` | 🔴 Red |
| Command | `[C]` | Dim |

#### Trend Arrows

| Arrow | Meaning |
|-------|---------|
| `(new)` | First session (no previous data to compare) |
| `↗` | Activity increased (>20% more changes) |
| `→` | Similar activity level (±20%) |
| `↘` | Activity decreased (>20% fewer changes) |

## Design Philosophy

This statusline prioritizes **developer productivity** by displaying actionable metrics:

- **Code Productivity** - Track actual work output with line change statistics
- **Performance Awareness** - Monitor API response times to identify slowdowns
- **Cost Management** - Stay within budget with real-time cost tracking
- **Development Context** - Git branch and status at a glance

All metrics are derived from Claude Code's built-in session data, requiring no external APIs or dependencies.

## Data Sources

The statusline extracts data from Claude Code's session context (passed via stdin):

| Metric | Source Field |
|--------|--------------|
| Lines Added | `cost.total_lines_added` |
| Lines Removed | `cost.total_lines_removed` |
| API Duration | `cost.total_api_duration_ms` |
| Session Cost | `cost.total_cost_usd` |
| Session Duration | `cost.total_duration_ms` |
| Working Directory | `workspace.current_dir` |
| AI Model | `model.display_name` |
| Context Window | `context_window.used_percentage` |
| Context Size | `context_window.context_window_size` |
| Input Tokens | `context_window.total_input_tokens` |
| Output Tokens | `context_window.total_output_tokens` |
| 200K+ Flag | `exceeds_200k_tokens` |
| Vim Mode | `vim.mode` |
| Output Style | `output_style.name` |

## Troubleshooting

### No metrics showing?

- Ensure you're using Claude Code v1.2.0 or higher
- Verify cost tracking is enabled in Claude Code
- Check logs: `~/.cache/claude-statusline/logs/`

### Colors not working?

- Check if `NO_COLOR` environment variable is set
- Enable debug mode: `STATUSLINE_DEBUG=1`
- Verify terminal supports ANSI colors

### Trend arrows not appearing?

- Arrows require at least two sessions for comparison
- Cache location: `~/.cache/claude-statusline/session_stats.json`
- Cache lifetime: 24 hours

### Git dirty status not showing?

- Ensure `git` is installed and in PATH
- Check that working directory is a git repository
- Verify git permissions

### Invalid configuration values?

The statusline gracefully handles invalid configuration:
- Invalid `STATUSLINE_COST_THRESHOLD` → defaults to `0.50`
- Invalid `STATUSLINE_LOG_LEVEL` → defaults to `WARNING`
- Missing cache directory → continues without trend tracking

## Development

### Testing Locally

```bash
# Test with mock data
echo '{
  "model": {"display_name": "Sonnet 4.5"},
  "workspace": {"current_dir": "/path/to/project"},
  "cost": {
    "total_cost_usd": 0.125,
    "total_duration_ms": 300000,
    "total_lines_added": 127,
    "total_lines_removed": 43,
    "total_api_duration_ms": 5000
  },
  "context_window": {
    "used_percentage": 42.5,
    "remaining_percentage": 57.5,
    "total_input_tokens": 45000,
    "total_output_tokens": 12000
  },
  "vim": {"mode": "normal"},
  "output_style": {"name": "concise"}
}' | python3 statusline-hz.py
```

### Running Unit Tests

```bash
# Run all tests
python3 tests/test_statusline.py -v

# Or with pytest (if installed)
pytest tests/test_statusline.py -v
```

### Enable Debug Logging

```bash
export STATUSLINE_LOG_LEVEL=DEBUG
export STATUSLINE_DEBUG=1
```

Logs are written to: `~/.cache/claude-statusline/logs/statusline-YYYYMMDD.log`

### Performance Notes

According to [Claude Code official documentation](https://code.claude.com/docs/en/statusline):
- Statusline updates are throttled to every 300ms
- Git status checks are cached for 5 seconds to stay within this budget
- Log cleanup runs once per day to minimize I/O overhead

## License

MIT License - See [LICENSE](LICENSE) file for details.

## Acknowledgments

Built with insights from:
- [Claude Code Official Documentation](https://code.claude.com/docs/en/statusline)
- Terminal statusline best practices
- Developer productivity metrics research

---

**Note**: This is an independent project and is not officially affiliated with Anthropic or Claude Code.
