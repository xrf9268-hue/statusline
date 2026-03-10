#!/usr/bin/env python3
"""
Claude Code Productivity Statusline
Displays code metrics, performance stats, and development context
Replaces weather data with actual coding productivity indicators
"""

import os
import sys
import json
import time
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List
import subprocess

# ===================== Cross-platform File Locking =====================
# Detect available locking mechanism once at module load
_lock_impl = None  # 'fcntl', 'msvcrt', or None
try:
    import fcntl as _fcntl_mod
    _lock_impl = 'fcntl'
except ImportError:
    try:
        import msvcrt as _msvcrt_mod
        _lock_impl = 'msvcrt'
    except ImportError:
        pass  # No locking available - degrade gracefully


def _flock(f, exclusive=False):
    """Acquire file lock (cross-platform: fcntl -> msvcrt -> no-op)"""
    if _lock_impl == 'fcntl':
        _fcntl_mod.flock(f.fileno(), _fcntl_mod.LOCK_EX if exclusive else _fcntl_mod.LOCK_SH)
    elif _lock_impl == 'msvcrt':
        # msvcrt only supports exclusive locks; shared lock not available on Windows
        _msvcrt_mod.locking(f.fileno(), _msvcrt_mod.LK_LOCK, 1)


def _funlock(f):
    """Release file lock (cross-platform: fcntl -> msvcrt -> no-op)"""
    if _lock_impl == 'fcntl':
        _fcntl_mod.flock(f.fileno(), _fcntl_mod.LOCK_UN)
    elif _lock_impl == 'msvcrt':
        _msvcrt_mod.locking(f.fileno(), _msvcrt_mod.LK_UNLCK, 1)

# ===================== Constants =====================
# Time constants
SECONDS_PER_DAY = 86400
CACHE_EXPIRY_SECONDS = SECONDS_PER_DAY  # 24 hours
LOG_RETENTION_DAYS = 7

# Performance thresholds (for cumulative API time in session)
# These are higher than single-request thresholds since they're cumulative
PERF_FAST_MS = 10000       # < 10s cumulative = green (fast session)
PERF_MODERATE_MS = 60000   # < 60s cumulative = yellow (normal session)
# > 60s = red (long/slow session)

# Context window thresholds
CTX_LOW = 50    # < 50% = green
CTX_MED = 75    # < 75% = yellow, >= 75% = red

# Trend analysis threshold
TREND_THRESHOLD = 0.2  # 20% change triggers trend arrow

# Git settings
GIT_TIMEOUT_SECONDS = 1
GIT_CACHE_TTL_SECONDS = 5.0  # Cache git status for 5 seconds

# Vim mode display mapping
VIM_MODE_MAP = {
    'NORMAL': ('N', 'GREEN'),
    'INSERT': ('I', 'YELLOW'),
    'VISUAL': ('V', 'CYAN'),
    'REPLACE': ('R', 'RED'),
    'COMMAND': ('C', 'DIM'),
}

# Default layout segments
DEFAULT_LAYOUT = 'vim,time,model,dir,cost,lines,api'

# ===================== Colors =====================
class Colors:
    """ANSI color codes for terminal output (eye-friendly palette)"""

    _enabled = 'NO_COLOR' not in os.environ

    ORANGE = '\033[38;5;173m' if _enabled else ''   # Model name
    CYAN = '\033[38;5;87m' if _enabled else ''      # Cost/metrics
    DIM = '\033[2m' if _enabled else ''             # Secondary info
    GREEN = '\033[38;5;78m' if _enabled else ''     # Positive/fast
    YELLOW = '\033[38;5;185m' if _enabled else ''   # Warning/moderate
    RED = '\033[38;5;167m' if _enabled else ''      # Alert/slow
    RESET = '\033[0m' if _enabled else ''

    @classmethod
    def disable(cls):
        """Disable all colors"""
        cls.ORANGE = cls.CYAN = cls.DIM = ''
        cls.GREEN = cls.YELLOW = cls.RED = cls.RESET = ''

    @classmethod
    def get(cls, name: str) -> str:
        """Get color by name string"""
        return getattr(cls, name, '')

# ===================== Configuration =====================
class Config:
    """Configuration management for statusline"""

    VALID_LOG_LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL', 'OFF']

    def __init__(self):
        # Cost Alert Configuration - with error handling
        try:
            self.cost_threshold = float(os.environ.get('STATUSLINE_COST_THRESHOLD', '0.50'))
            if self.cost_threshold < 0:
                self.cost_threshold = 0.50
        except (ValueError, TypeError):
            self.cost_threshold = 0.50  # Fallback to default

        # Cache directory for trends
        self.cache_dir_base = Path.home() / '.cache' / 'claude-statusline'
        self.stats_cache_file = self.cache_dir_base / 'session_stats.json'

        # Logging - default to WARNING for better performance
        log_level_str = os.environ.get('STATUSLINE_LOG_LEVEL', 'WARNING').upper()
        self.log_level = log_level_str if log_level_str in self.VALID_LOG_LEVELS else 'WARNING'
        self.log_dir = self.cache_dir_base / 'logs'

        # Debug Mode
        self.debug = os.environ.get('STATUSLINE_DEBUG', '0') == '1'

        # Color Output - also update Colors class
        self.no_color = 'NO_COLOR' in os.environ
        if self.no_color:
            Colors.disable()

        # Feature toggles
        self.show_tokens = os.environ.get('STATUSLINE_SHOW_TOKENS', '0') == '1'
        self.show_burnrate = os.environ.get('STATUSLINE_SHOW_BURNRATE', '0') == '1'

        # Layout configuration
        self.layout = os.environ.get('STATUSLINE_LAYOUT', DEFAULT_LAYOUT).split(',')

    def ensure_directories(self) -> bool:
        """Ensure required directories exist (initialization)"""
        success = True
        try:
            self.cache_dir_base.mkdir(parents=True, exist_ok=True)
        except (OSError, PermissionError) as e:
            logging.warning(f"Cache directory unavailable: {e}")
            success = False
        return success

    def is_valid(self) -> bool:
        """Check if configuration is valid"""
        if self.cost_threshold < 0:
            return False
        if self.log_level not in self.VALID_LOG_LEVELS:
            return False
        return True

# ===================== Data Classes =====================
@dataclass
class ClaudeContext:
    """Parsed Claude Code context data"""
    model: str = 'Claude'
    dir: str = '.'
    cwd: str = '.'
    branch: str = ''
    detached: bool = False
    cost_usd: float = 0.0
    cost_str: Optional[str] = None
    duration: Optional[str] = None
    duration_seconds: float = 0.0
    lines_added: int = 0
    lines_removed: int = 0
    api_duration_ms: int = 0
    # Context window
    ctx_used_pct: Optional[float] = None
    ctx_remaining_pct: Optional[float] = None
    ctx_window_size: Optional[int] = None
    exceeds_200k: bool = False
    # Tokens
    input_tokens: int = 0
    output_tokens: int = 0
    # Vim mode
    vim_mode: Optional[str] = None
    # Output style
    output_style: Optional[str] = None

# ===================== Logging Setup =====================
def _should_run_log_cleanup(log_dir: Path) -> bool:
    """Check if log cleanup should run (once per day)"""
    marker_file = log_dir / '.last_cleanup'
    try:
        if marker_file.exists():
            last_cleanup = marker_file.stat().st_mtime
            if time.time() - last_cleanup < SECONDS_PER_DAY:
                return False
    except OSError:
        pass
    return True


def _mark_cleanup_done(log_dir: Path):
    """Mark that cleanup was performed"""
    marker_file = log_dir / '.last_cleanup'
    try:
        marker_file.touch()
    except OSError:
        pass


def setup_logging(config: Config):
    """Setup logging system"""
    if config.log_level == 'OFF':
        logging.disable(logging.CRITICAL)
        return

    try:
        config.log_dir.mkdir(parents=True, exist_ok=True)
        log_file = config.log_dir / f"statusline-{datetime.now().strftime('%Y%m%d')}.log"

        # Configure logging (log_level already validated in Config)
        logging.basicConfig(
            level=getattr(logging, config.log_level),
            format='[%(asctime)s] [%(levelname)s] [%(funcName)s] %(message)s',
            handlers=[logging.FileHandler(log_file)]
        )

        # Log rotation - only run once per day for performance
        if _should_run_log_cleanup(config.log_dir):
            retention_cutoff = time.time() - (LOG_RETENTION_DAYS * SECONDS_PER_DAY)
            for old_log in config.log_dir.glob("statusline-*.log*"):
                try:
                    if old_log.stat().st_mtime < retention_cutoff:
                        old_log.unlink()
                except (OSError, PermissionError):
                    pass  # Ignore errors deleting old logs
            _mark_cleanup_done(config.log_dir)

    except (OSError, PermissionError):
        # If logging setup fails, disable logging but continue
        logging.disable(logging.CRITICAL)

# ===================== Git Status Checker =====================
class GitStatusChecker:
    """Check git repository status with caching for performance"""

    # Cache: {cwd: (is_dirty, timestamp)}
    _cache: Dict[str, Tuple[bool, float]] = {}

    @classmethod
    def check_dirty_status(cls, cwd: str) -> bool:
        """Check if git repo has uncommitted changes (with caching)"""
        now = time.time()

        # Check cache first
        if cwd in cls._cache:
            is_dirty, cached_at = cls._cache[cwd]
            if now - cached_at < GIT_CACHE_TTL_SECONDS:
                return is_dirty

        # Cache miss or expired - perform actual check
        is_dirty = cls._check_dirty_impl(cwd)
        cls._cache[cwd] = (is_dirty, now)
        return is_dirty

    @staticmethod
    def _check_dirty_impl(cwd: str) -> bool:
        """Actual git dirty status check implementation"""
        try:
            git_dir = Path(cwd) / '.git'
            if not git_dir.exists():
                return False

            # Quick check using git status --porcelain (with --no-optional-locks to avoid blocking)
            result = subprocess.run(
                ['git', '--no-optional-locks', 'status', '--porcelain'],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=GIT_TIMEOUT_SECONDS
            )

            # If output is not empty, there are uncommitted changes
            return bool(result.stdout.strip())

        except FileNotFoundError:
            logging.debug("Git command not found")
            return False
        except subprocess.TimeoutExpired:
            logging.debug("Git status check timed out")
            return False
        except (OSError, subprocess.SubprocessError) as e:
            logging.debug(f"Failed to check git status: {e}")
            return False

# ===================== Stats Tracker =====================
class StatsTracker:
    """Track code change trends across sessions"""

    def __init__(self, config: Config):
        self.config = config
        self.cache_file = config.stats_cache_file

    def _load_previous_stats(self) -> Optional[Dict[str, Any]]:
        """Load previous session stats from cache"""
        try:
            if self.cache_file.exists():
                cache_age = time.time() - self.cache_file.stat().st_mtime
                if cache_age < CACHE_EXPIRY_SECONDS:
                    with open(self.cache_file, 'r') as f:
                        _flock(f, exclusive=False)
                        data = json.load(f)
                        _funlock(f)
                        return data
        except (json.JSONDecodeError, OSError, IOError) as e:
            logging.debug(f"Failed to load previous stats: {e}")
        return None

    def _save_current_stats(self, lines_added: int, lines_removed: int):
        """Save current session stats to cache with file locking"""
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                'lines_added': lines_added,
                'lines_removed': lines_removed,
                'timestamp': time.time()
            }

            # Use temp file + atomic rename for safety
            temp_file = self.cache_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                _flock(f, exclusive=True)
                json.dump(data, f)
                f.flush()
                os.fsync(f.fileno())
                _funlock(f)

            temp_file.rename(self.cache_file)

        except (OSError, IOError) as e:
            logging.debug(f"Failed to save stats: {e}")

    def calculate_trend(self, current_added: int, current_removed: int) -> str:
        """Calculate trend arrow (pure function, no side effects)"""
        prev = self._load_previous_stats()

        if not prev:
            return ' (new)'  # First session indicator

        current_total = current_added + current_removed
        prev_total = prev.get('lines_added', 0) + prev.get('lines_removed', 0)

        if prev_total == 0:
            return ' ↗' if current_total > 0 else ''

        ratio = current_total / prev_total
        if ratio > 1 + TREND_THRESHOLD:
            return ' ↗'
        elif ratio < 1 - TREND_THRESHOLD:
            return ' ↘'
        return ' →'

    def save_session_stats(self, lines_added: int, lines_removed: int):
        """Save current session stats (explicit side effect)"""
        self._save_current_stats(lines_added, lines_removed)

    def get_trend_and_save(self, current_added: int, current_removed: int) -> str:
        """Get trend arrow and save stats (combined operation with clear naming)"""
        trend = self.calculate_trend(current_added, current_removed)
        self.save_session_stats(current_added, current_removed)
        return trend

# ===================== Formatting Helpers =====================
def format_tokens(count: int) -> str:
    """Format token count with K/M suffix"""
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    elif count >= 1000:
        return f"{count / 1000:.1f}K"
    return str(count)


def format_ctx_color(pct: float) -> str:
    """Return colored context percentage string"""
    if pct < CTX_LOW:
        color = Colors.GREEN
    elif pct < CTX_MED:
        color = Colors.YELLOW
    else:
        color = Colors.RED
    return f"{color}ctx:{pct:.0f}%{Colors.RESET}"

# ===================== Claude Context Parser =====================
def parse_claude_context() -> ClaudeContext:
    """Parse Claude Code context from stdin - enhanced with productivity metrics"""
    ctx = ClaudeContext()

    try:
        input_data = sys.stdin.read()
        if input_data:
            data = json.loads(input_data)

            # Parse model
            if 'model' in data:
                ctx.model = data['model'].get('display_name') or data['model'].get('id', 'Claude')

            # Parse directory
            if 'workspace' in data:
                cwd = data['workspace'].get('current_dir', '.')
                ctx.cwd = cwd
                ctx.dir = Path(cwd).name

                # Check for git branch (handle detached HEAD)
                git_head = Path(cwd) / '.git' / 'HEAD'
                if git_head.exists():
                    try:
                        content = git_head.read_text().strip()
                        if content.startswith('ref: '):
                            # Normal branch reference
                            ctx.branch = content.split('/')[-1]
                        else:
                            # Detached HEAD - show short commit hash
                            ctx.branch = content[:7]
                            ctx.detached = True
                    except (OSError, IOError):
                        pass

            # Parse cost metrics
            if 'cost' in data:
                # Cost in USD
                cost_usd = data['cost'].get('total_cost_usd') or data['cost'].get('usd')
                if cost_usd is not None:
                    ctx.cost_usd = float(cost_usd)
                    ctx.cost_str = f"${cost_usd:.3f}"

                # Parse duration (handle both ms and sec formats)
                duration_value = data['cost'].get('total_duration_ms') or data['cost'].get('duration_sec')
                if duration_value is not None and duration_value > 0:
                    # Convert to seconds if value was in milliseconds
                    if data['cost'].get('total_duration_ms'):
                        duration_seconds = duration_value / 1000
                    else:
                        duration_seconds = duration_value

                    ctx.duration_seconds = duration_seconds
                    minutes = int(duration_seconds // 60)
                    if minutes > 0:
                        ctx.duration = f"{minutes}m"
                    else:
                        seconds = int(duration_seconds)
                        ctx.duration = f"{seconds}s"

                # Parse code change stats
                lines_added = data['cost'].get('total_lines_added')
                if lines_added is not None:
                    ctx.lines_added = int(lines_added)

                lines_removed = data['cost'].get('total_lines_removed')
                if lines_removed is not None:
                    ctx.lines_removed = int(lines_removed)

                # Parse API performance (cumulative time)
                api_duration = data['cost'].get('total_api_duration_ms')
                if api_duration is not None:
                    ctx.api_duration_ms = int(api_duration)

            # Parse context window
            cw = data.get('context_window')
            if cw:
                used_pct = cw.get('used_percentage')
                if used_pct is not None:
                    ctx.ctx_used_pct = float(used_pct)
                remaining_pct = cw.get('remaining_percentage')
                if remaining_pct is not None:
                    ctx.ctx_remaining_pct = float(remaining_pct)
                # Token counts
                input_tokens = cw.get('total_input_tokens')
                if input_tokens is not None:
                    ctx.input_tokens = int(input_tokens)
                output_tokens = cw.get('total_output_tokens')
                if output_tokens is not None:
                    ctx.output_tokens = int(output_tokens)
                ctx_size = cw.get('context_window_size')
                if ctx_size is not None:
                    ctx.ctx_window_size = int(ctx_size)

            # Parse exceeds_200k_tokens flag
            if data.get('exceeds_200k_tokens'):
                ctx.exceeds_200k = True

            # Parse vim mode
            vim_data = data.get('vim')
            if vim_data:
                vim_mode = vim_data.get('mode')
                if vim_mode:
                    ctx.vim_mode = vim_mode.upper()

            # Parse output style
            style_data = data.get('output_style')
            if style_data:
                style_name = style_data.get('name')
                if style_name:
                    ctx.output_style = style_name

    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
        logging.debug(f"Failed to parse Claude context: {e}")

    return ctx

# ===================== Segment Builders =====================
def _build_vim_segment(ctx: ClaudeContext) -> Optional[str]:
    """Build vim mode indicator segment"""
    if not ctx.vim_mode:
        return None
    abbr, color_name = VIM_MODE_MAP.get(ctx.vim_mode, (ctx.vim_mode[0], 'DIM'))
    color = Colors.get(color_name)
    return f"[{color}{abbr}{Colors.RESET}]"


def _build_time_segment() -> str:
    """Build time segment"""
    return f"⏰ {datetime.now().strftime('%H:%M')}"


def _build_model_segment(ctx: ClaudeContext) -> str:
    """Build model name segment (with optional output style)"""
    model_str = f"{Colors.ORANGE}{ctx.model}{Colors.RESET}"
    if ctx.output_style:
        model_str += f" {Colors.DIM}({ctx.output_style}){Colors.RESET}"
    return model_str


def _build_dir_segment(ctx: ClaudeContext, is_dirty: bool) -> str:
    """Build directory and branch segment"""
    segment = f"{Colors.DIM}{ctx.dir}{Colors.RESET}"
    if ctx.branch:
        if ctx.detached:
            segment += f":{Colors.DIM}@{ctx.branch}{Colors.RESET}"
        else:
            segment += f":{ctx.branch}"
        if is_dirty:
            segment += f"{Colors.RED}●{Colors.RESET}"
    return segment


def _build_cost_segment(ctx: ClaudeContext, config: Config) -> Optional[str]:
    """Build cost and duration bracket segment"""
    metrics = []
    if ctx.cost_str:
        cost_display = ctx.cost_str
        if ctx.cost_usd > config.cost_threshold:
            cost_display += f" {Colors.RED}⚠️{Colors.RESET}"
        metrics.append(f"{Colors.CYAN}{cost_display}{Colors.RESET}")

    if ctx.duration:
        metrics.append(f"{Colors.CYAN}{ctx.duration}{Colors.RESET}")

    # Context window percentage (inside brackets with cost)
    if ctx.ctx_used_pct is not None:
        ctx_str = format_ctx_color(ctx.ctx_used_pct)
        if ctx.exceeds_200k:
            ctx_str += f" {Colors.RED}200K+{Colors.RESET}"
        metrics.append(ctx_str)

    if not metrics:
        return None
    return f"[{' '.join(metrics)}]"


def _build_context_segment(ctx: ClaudeContext) -> Optional[str]:
    """Build standalone context window segment (when not in cost bracket)"""
    if ctx.ctx_used_pct is not None:
        return format_ctx_color(ctx.ctx_used_pct)
    return None


def _build_tokens_segment(ctx: ClaudeContext) -> Optional[str]:
    """Build token count segment"""
    if ctx.input_tokens > 0 or ctx.output_tokens > 0:
        return f"{Colors.DIM}tok:{format_tokens(ctx.input_tokens)}/{format_tokens(ctx.output_tokens)}{Colors.RESET}"
    return None


def _build_lines_segment(ctx: ClaudeContext, trend_arrow: str) -> str:
    """Build code change statistics segment"""
    if ctx.lines_added > 0 or ctx.lines_removed > 0:
        return f"{Colors.GREEN}📝 +{ctx.lines_added}/-{ctx.lines_removed}{trend_arrow}{Colors.RESET}"
    return f"{Colors.DIM}📝 0/0{trend_arrow}{Colors.RESET}"


def _build_api_segment(ctx: ClaudeContext) -> Optional[str]:
    """Build API performance segment"""
    api_duration = ctx.api_duration_ms
    if api_duration <= 0:
        return None

    if api_duration < 1000:
        api_str = f"{api_duration}ms"
    elif api_duration < 60000:
        api_str = f"{api_duration/1000:.1f}s"
    else:
        api_str = f"{api_duration/60000:.1f}m"

    if api_duration < PERF_FAST_MS:
        return f"{Colors.GREEN}⚡{api_str}{Colors.RESET}"
    elif api_duration < PERF_MODERATE_MS:
        return f"{Colors.YELLOW}⚡{api_str}{Colors.RESET}"
    return f"{Colors.RED}⚡{api_str}{Colors.RESET}"


def _build_burnrate_segment(ctx: ClaudeContext) -> Optional[str]:
    """Build cost burn rate segment"""
    if ctx.duration_seconds > 120 and ctx.cost_usd > 0:
        rate = ctx.cost_usd / (ctx.duration_seconds / 60)
        return f"{Colors.DIM}({rate:.2f}/m){Colors.RESET}"
    return None

# ===================== Main Function =====================
def main():
    """Main entry point - Productivity-focused statusline"""
    # Initialize configuration
    config = Config()

    # Setup logging
    setup_logging(config)
    logging.info("Productivity StatusLine started")

    # Ensure directories exist and validate config
    config.ensure_directories()
    if not config.is_valid():
        print("ERROR: Configuration invalid")
        sys.exit(1)

    # Parse Claude context
    context = parse_claude_context()
    logging.debug(f"Context: {context}")

    # Check git dirty status
    is_dirty = GitStatusChecker.check_dirty_status(context.cwd)

    # Get code change trend
    tracker = StatsTracker(config)
    trend_arrow = tracker.get_trend_and_save(context.lines_added, context.lines_removed)

    # Build segments based on layout configuration
    layout = config.layout

    # Segment builders map
    segment_builders = {
        'vim': lambda: _build_vim_segment(context),
        'time': lambda: _build_time_segment(),
        'model': lambda: _build_model_segment(context),
        'dir': lambda: _build_dir_segment(context, is_dirty),
        'cost': lambda: _build_cost_segment(context, config),
        'context': lambda: _build_context_segment(context),
        'tokens': lambda: _build_tokens_segment(context) if config.show_tokens else None,
        'lines': lambda: _build_lines_segment(context, trend_arrow),
        'api': lambda: _build_api_segment(context),
        'burnrate': lambda: _build_burnrate_segment(context) if config.show_burnrate else None,
    }

    # When 'cost' is in layout, context is included inside the cost bracket,
    # so skip standalone 'context' segment to avoid duplication
    skip_standalone_context = 'cost' in layout

    parts: List[str] = []
    # Header parts (vim, time, model, dir) are joined with spaces
    # The rest are joined with " | "
    header_keys = {'vim', 'time', 'model', 'dir'}

    header_parts: List[str] = []
    metric_parts: List[str] = []

    for segment_name in layout:
        segment_name = segment_name.strip()
        if skip_standalone_context and segment_name == 'context':
            continue
        builder = segment_builders.get(segment_name)
        if not builder:
            continue
        result = builder()
        if result is None:
            continue
        if segment_name in header_keys:
            header_parts.append(result)
        else:
            metric_parts.append(result)

    # Build final output
    if header_parts and metric_parts:
        output = f"{' '.join(header_parts)} | {' | '.join(metric_parts)}"
    elif header_parts:
        output = f"{' '.join(header_parts)} | {Colors.DIM}Initializing...{Colors.RESET}"
    elif metric_parts:
        output = ' | '.join(metric_parts)
    else:
        output = f"{Colors.DIM}Initializing...{Colors.RESET}"

    # Output (first line only, as per official docs)
    print(output)

    logging.info(f"Productivity status displayed: +{context.lines_added}/-{context.lines_removed}, API: {context.api_duration_ms}ms")
    logging.info("Execution completed")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        logging.error(f"Unhandled exception: {e}", exc_info=True)
        print(f"ERROR: {e}")
        sys.exit(1)
