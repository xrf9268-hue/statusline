#!/usr/bin/env python3
"""
Unit tests for Claude Code Productivity Statusline
"""

import unittest
import json
import os
import sys
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import module by executing it (since it has a hyphen in the name)
import importlib.util
spec = importlib.util.spec_from_file_location("statusline", Path(__file__).parent.parent / "statusline-hz.py")
statusline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(statusline)


class TestConstants(unittest.TestCase):
    """Test that constants are properly defined"""

    def test_time_constants(self):
        self.assertEqual(statusline.SECONDS_PER_DAY, 86400)
        self.assertEqual(statusline.CACHE_EXPIRY_SECONDS, 86400)
        self.assertEqual(statusline.LOG_RETENTION_DAYS, 7)

    def test_performance_thresholds(self):
        self.assertEqual(statusline.PERF_FAST_MS, 10000)
        self.assertEqual(statusline.PERF_MODERATE_MS, 60000)

    def test_context_window_thresholds(self):
        self.assertEqual(statusline.CTX_LOW, 50)
        self.assertEqual(statusline.CTX_MED, 75)

    def test_trend_threshold(self):
        self.assertEqual(statusline.TREND_THRESHOLD, 0.2)

    def test_git_settings(self):
        self.assertEqual(statusline.GIT_TIMEOUT_SECONDS, 1)
        self.assertEqual(statusline.GIT_CACHE_TTL_SECONDS, 5.0)

    def test_vim_mode_map(self):
        self.assertIn('NORMAL', statusline.VIM_MODE_MAP)
        self.assertIn('INSERT', statusline.VIM_MODE_MAP)
        self.assertIn('VISUAL', statusline.VIM_MODE_MAP)
        self.assertIn('REPLACE', statusline.VIM_MODE_MAP)


class TestColors(unittest.TestCase):
    """Test Colors class functionality"""

    def test_colors_defined(self):
        """Verify all color codes are defined"""
        self.assertIsNotNone(statusline.Colors.ORANGE)
        self.assertIsNotNone(statusline.Colors.CYAN)
        self.assertIsNotNone(statusline.Colors.DIM)
        self.assertIsNotNone(statusline.Colors.GREEN)
        self.assertIsNotNone(statusline.Colors.YELLOW)
        self.assertIsNotNone(statusline.Colors.RED)
        self.assertIsNotNone(statusline.Colors.RESET)

    def test_disable_colors(self):
        """Test that disable() clears all colors"""
        original_orange = statusline.Colors.ORANGE
        statusline.Colors.disable()
        self.assertEqual(statusline.Colors.ORANGE, '')
        self.assertEqual(statusline.Colors.RESET, '')
        # Restore
        statusline.Colors.ORANGE = original_orange

    def test_get_color_by_name(self):
        """Test Colors.get() method"""
        self.assertEqual(statusline.Colors.get('GREEN'), statusline.Colors.GREEN)
        self.assertEqual(statusline.Colors.get('NONEXISTENT'), '')


class TestConfig(unittest.TestCase):
    """Test Config class"""

    def test_default_values(self):
        """Test default configuration values"""
        with patch.dict(os.environ, {}, clear=True):
            config = statusline.Config()
            self.assertEqual(config.cost_threshold, 0.50)
            self.assertEqual(config.log_level, 'WARNING')
            self.assertFalse(config.debug)
            self.assertFalse(config.show_tokens)
            self.assertFalse(config.show_burnrate)

    def test_custom_cost_threshold(self):
        with patch.dict(os.environ, {'STATUSLINE_COST_THRESHOLD': '1.25'}):
            config = statusline.Config()
            self.assertEqual(config.cost_threshold, 1.25)

    def test_invalid_cost_threshold_fallback(self):
        with patch.dict(os.environ, {'STATUSLINE_COST_THRESHOLD': 'invalid'}):
            config = statusline.Config()
            self.assertEqual(config.cost_threshold, 0.50)

    def test_negative_cost_threshold_fallback(self):
        with patch.dict(os.environ, {'STATUSLINE_COST_THRESHOLD': '-5'}):
            config = statusline.Config()
            self.assertEqual(config.cost_threshold, 0.50)

    def test_valid_log_levels(self):
        for level in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL', 'OFF']:
            with patch.dict(os.environ, {'STATUSLINE_LOG_LEVEL': level}):
                config = statusline.Config()
                self.assertEqual(config.log_level, level)

    def test_invalid_log_level_fallback(self):
        with patch.dict(os.environ, {'STATUSLINE_LOG_LEVEL': 'INVALID'}):
            config = statusline.Config()
            self.assertEqual(config.log_level, 'WARNING')

    def test_debug_mode(self):
        with patch.dict(os.environ, {'STATUSLINE_DEBUG': '1'}):
            config = statusline.Config()
            self.assertTrue(config.debug)

    def test_show_tokens_env(self):
        with patch.dict(os.environ, {'STATUSLINE_SHOW_TOKENS': '1'}):
            config = statusline.Config()
            self.assertTrue(config.show_tokens)

    def test_show_burnrate_env(self):
        with patch.dict(os.environ, {'STATUSLINE_SHOW_BURNRATE': '1'}):
            config = statusline.Config()
            self.assertTrue(config.show_burnrate)

    def test_custom_layout(self):
        with patch.dict(os.environ, {'STATUSLINE_LAYOUT': 'time,model,api'}):
            config = statusline.Config()
            self.assertEqual(config.layout, ['time', 'model', 'api'])

    def test_is_valid(self):
        config = statusline.Config()
        self.assertTrue(config.is_valid())


class TestClaudeContext(unittest.TestCase):
    """Test ClaudeContext dataclass"""

    def test_default_values(self):
        ctx = statusline.ClaudeContext()
        self.assertEqual(ctx.model, 'Claude')
        self.assertEqual(ctx.dir, '.')
        self.assertEqual(ctx.cost_usd, 0.0)
        self.assertIsNone(ctx.ctx_used_pct)
        self.assertIsNone(ctx.vim_mode)
        self.assertIsNone(ctx.output_style)
        self.assertEqual(ctx.input_tokens, 0)
        self.assertEqual(ctx.output_tokens, 0)

    def test_custom_values(self):
        ctx = statusline.ClaudeContext(model='Sonnet 4.5', ctx_used_pct=65.0, vim_mode='NORMAL')
        self.assertEqual(ctx.model, 'Sonnet 4.5')
        self.assertEqual(ctx.ctx_used_pct, 65.0)
        self.assertEqual(ctx.vim_mode, 'NORMAL')


class TestParseClaudeContext(unittest.TestCase):
    """Test parse_claude_context function"""

    def test_parse_valid_json(self):
        mock_input = json.dumps({
            'model': {'display_name': 'Sonnet 4.5'},
            'workspace': {'current_dir': '/test/path'},
            'cost': {
                'total_cost_usd': 0.125,
                'total_duration_ms': 300000,
                'total_lines_added': 100,
                'total_lines_removed': 50,
                'total_api_duration_ms': 5000
            }
        })

        with patch('sys.stdin', StringIO(mock_input)):
            result = statusline.parse_claude_context()

        self.assertEqual(result.model, 'Sonnet 4.5')
        self.assertEqual(result.lines_added, 100)
        self.assertEqual(result.lines_removed, 50)
        self.assertEqual(result.cost_usd, 0.125)
        self.assertEqual(result.api_duration_ms, 5000)
        self.assertEqual(result.duration, '5m')

    def test_parse_empty_input(self):
        with patch('sys.stdin', StringIO('')):
            result = statusline.parse_claude_context()
        self.assertEqual(result.model, 'Claude')
        self.assertEqual(result.lines_added, 0)

    def test_parse_invalid_json(self):
        with patch('sys.stdin', StringIO('not valid json')):
            result = statusline.parse_claude_context()
        self.assertEqual(result.model, 'Claude')

    def test_duration_under_one_minute(self):
        mock_input = json.dumps({
            'cost': {'total_duration_ms': 45000}
        })
        with patch('sys.stdin', StringIO(mock_input)):
            result = statusline.parse_claude_context()
        self.assertEqual(result.duration, '45s')

    def test_parse_context_window(self):
        """Test parsing context_window fields"""
        mock_input = json.dumps({
            'context_window': {
                'used_percentage': 42.5,
                'remaining_percentage': 57.5,
                'total_input_tokens': 45000,
                'total_output_tokens': 12000
            }
        })
        with patch('sys.stdin', StringIO(mock_input)):
            result = statusline.parse_claude_context()
        self.assertAlmostEqual(result.ctx_used_pct, 42.5)
        self.assertAlmostEqual(result.ctx_remaining_pct, 57.5)
        self.assertEqual(result.input_tokens, 45000)
        self.assertEqual(result.output_tokens, 12000)

    def test_parse_context_window_null(self):
        """Test that null context_window is handled gracefully"""
        mock_input = json.dumps({
            'context_window': {
                'used_percentage': None,
                'remaining_percentage': None
            }
        })
        with patch('sys.stdin', StringIO(mock_input)):
            result = statusline.parse_claude_context()
        self.assertIsNone(result.ctx_used_pct)
        self.assertIsNone(result.ctx_remaining_pct)

    def test_parse_context_window_missing(self):
        """Test that missing context_window doesn't crash"""
        mock_input = json.dumps({'model': {'display_name': 'Test'}})
        with patch('sys.stdin', StringIO(mock_input)):
            result = statusline.parse_claude_context()
        self.assertIsNone(result.ctx_used_pct)

    def test_parse_vim_mode(self):
        """Test parsing vim mode"""
        mock_input = json.dumps({
            'vim': {'mode': 'normal'}
        })
        with patch('sys.stdin', StringIO(mock_input)):
            result = statusline.parse_claude_context()
        self.assertEqual(result.vim_mode, 'NORMAL')

    def test_parse_vim_mode_missing(self):
        """Test that missing vim mode doesn't crash"""
        mock_input = json.dumps({'model': {'display_name': 'Test'}})
        with patch('sys.stdin', StringIO(mock_input)):
            result = statusline.parse_claude_context()
        self.assertIsNone(result.vim_mode)

    def test_parse_output_style(self):
        """Test parsing output style"""
        mock_input = json.dumps({
            'output_style': {'name': 'concise'}
        })
        with patch('sys.stdin', StringIO(mock_input)):
            result = statusline.parse_claude_context()
        self.assertEqual(result.output_style, 'concise')

    def test_parse_duration_seconds_stored(self):
        """Test that duration_seconds is stored for burn rate calculation"""
        mock_input = json.dumps({
            'cost': {'total_duration_ms': 120000}
        })
        with patch('sys.stdin', StringIO(mock_input)):
            result = statusline.parse_claude_context()
        self.assertEqual(result.duration_seconds, 120.0)


class TestFormatHelpers(unittest.TestCase):
    """Test formatting helper functions"""

    def test_format_tokens_small(self):
        self.assertEqual(statusline.format_tokens(500), '500')

    def test_format_tokens_thousands(self):
        self.assertEqual(statusline.format_tokens(45000), '45K')

    def test_format_tokens_millions(self):
        self.assertEqual(statusline.format_tokens(1500000), '1.5M')

    def test_format_ctx_color_low(self):
        result = statusline.format_ctx_color(30.0)
        self.assertIn('ctx:30%', result)
        self.assertIn(statusline.Colors.GREEN, result)

    def test_format_ctx_color_medium(self):
        result = statusline.format_ctx_color(60.0)
        self.assertIn('ctx:60%', result)
        self.assertIn(statusline.Colors.YELLOW, result)

    def test_format_ctx_color_high(self):
        result = statusline.format_ctx_color(80.0)
        self.assertIn('ctx:80%', result)
        self.assertIn(statusline.Colors.RED, result)

    def test_format_ctx_color_boundary_low(self):
        """Test boundary at CTX_LOW (50%)"""
        result_below = statusline.format_ctx_color(49.0)
        result_at = statusline.format_ctx_color(50.0)
        self.assertIn(statusline.Colors.GREEN, result_below)
        self.assertIn(statusline.Colors.YELLOW, result_at)

    def test_format_ctx_color_boundary_med(self):
        """Test boundary at CTX_MED (75%)"""
        result_below = statusline.format_ctx_color(74.0)
        result_at = statusline.format_ctx_color(75.0)
        self.assertIn(statusline.Colors.YELLOW, result_below)
        self.assertIn(statusline.Colors.RED, result_at)


class TestSegmentBuilders(unittest.TestCase):
    """Test segment builder functions"""

    def test_vim_segment_normal(self):
        ctx = statusline.ClaudeContext(vim_mode='NORMAL')
        result = statusline._build_vim_segment(ctx)
        self.assertIn('N', result)

    def test_vim_segment_insert(self):
        ctx = statusline.ClaudeContext(vim_mode='INSERT')
        result = statusline._build_vim_segment(ctx)
        self.assertIn('I', result)

    def test_vim_segment_visual(self):
        ctx = statusline.ClaudeContext(vim_mode='VISUAL')
        result = statusline._build_vim_segment(ctx)
        self.assertIn('V', result)

    def test_vim_segment_replace(self):
        ctx = statusline.ClaudeContext(vim_mode='REPLACE')
        result = statusline._build_vim_segment(ctx)
        self.assertIn('R', result)

    def test_vim_segment_none(self):
        ctx = statusline.ClaudeContext(vim_mode=None)
        result = statusline._build_vim_segment(ctx)
        self.assertIsNone(result)

    def test_vim_segment_unknown_mode(self):
        """Test unknown vim mode uses first character"""
        ctx = statusline.ClaudeContext(vim_mode='SELECT')
        result = statusline._build_vim_segment(ctx)
        self.assertIn('S', result)

    def test_model_segment_with_style(self):
        ctx = statusline.ClaudeContext(model='Sonnet 4.5', output_style='concise')
        result = statusline._build_model_segment(ctx)
        self.assertIn('Sonnet 4.5', result)
        self.assertIn('concise', result)

    def test_model_segment_without_style(self):
        ctx = statusline.ClaudeContext(model='Sonnet 4.5')
        result = statusline._build_model_segment(ctx)
        self.assertIn('Sonnet 4.5', result)
        self.assertNotIn('concise', result)

    def test_cost_segment_includes_context(self):
        ctx = statusline.ClaudeContext(cost_str='$0.125', cost_usd=0.125, ctx_used_pct=42.0)
        config = statusline.Config()
        result = statusline._build_cost_segment(ctx, config)
        self.assertIn('$0.125', result)
        self.assertIn('ctx:42%', result)

    def test_cost_segment_none_when_empty(self):
        ctx = statusline.ClaudeContext()
        config = statusline.Config()
        result = statusline._build_cost_segment(ctx, config)
        self.assertIsNone(result)

    def test_tokens_segment(self):
        ctx = statusline.ClaudeContext(input_tokens=45000, output_tokens=12000)
        result = statusline._build_tokens_segment(ctx)
        self.assertIn('tok:45K/12K', result)

    def test_tokens_segment_zero(self):
        ctx = statusline.ClaudeContext()
        result = statusline._build_tokens_segment(ctx)
        self.assertIsNone(result)

    def test_burnrate_segment(self):
        ctx = statusline.ClaudeContext(cost_usd=0.5, duration_seconds=300)
        result = statusline._build_burnrate_segment(ctx)
        self.assertIn('0.10/m', result)

    def test_burnrate_segment_short_session(self):
        """Burn rate not shown for sessions under 60s"""
        ctx = statusline.ClaudeContext(cost_usd=0.5, duration_seconds=30)
        result = statusline._build_burnrate_segment(ctx)
        self.assertIsNone(result)

    def test_lines_segment_with_changes(self):
        ctx = statusline.ClaudeContext(lines_added=100, lines_removed=50)
        result = statusline._build_lines_segment(ctx, ' ↗')
        self.assertIn('+100/-50', result)
        self.assertIn('↗', result)

    def test_lines_segment_no_changes(self):
        ctx = statusline.ClaudeContext()
        result = statusline._build_lines_segment(ctx, ' (new)')
        self.assertIn('0/0', result)

    def test_api_segment_fast(self):
        ctx = statusline.ClaudeContext(api_duration_ms=5000)
        result = statusline._build_api_segment(ctx)
        self.assertIn('5.0s', result)
        self.assertIn(statusline.Colors.GREEN, result)

    def test_api_segment_moderate(self):
        ctx = statusline.ClaudeContext(api_duration_ms=30000)
        result = statusline._build_api_segment(ctx)
        self.assertIn(statusline.Colors.YELLOW, result)

    def test_api_segment_slow(self):
        ctx = statusline.ClaudeContext(api_duration_ms=90000)
        result = statusline._build_api_segment(ctx)
        self.assertIn(statusline.Colors.RED, result)

    def test_api_segment_zero(self):
        ctx = statusline.ClaudeContext(api_duration_ms=0)
        result = statusline._build_api_segment(ctx)
        self.assertIsNone(result)


class TestStatsTracker(unittest.TestCase):
    """Test StatsTracker class"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config = MagicMock()
        self.config.stats_cache_file = Path(self.temp_dir) / 'session_stats.json'
        self.tracker = statusline.StatsTracker(self.config)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_first_session_indicator(self):
        trend = self.tracker.calculate_trend(100, 50)
        self.assertEqual(trend, ' (new)')

    def test_trend_increase(self):
        self.tracker.save_session_stats(100, 50)
        trend = self.tracker.calculate_trend(200, 100)
        self.assertEqual(trend, ' ↗')

    def test_trend_decrease(self):
        self.tracker.save_session_stats(200, 100)
        trend = self.tracker.calculate_trend(50, 25)
        self.assertEqual(trend, ' ↘')

    def test_trend_similar(self):
        self.tracker.save_session_stats(100, 50)
        trend = self.tracker.calculate_trend(110, 55)
        self.assertEqual(trend, ' →')


class TestGitStatusChecker(unittest.TestCase):
    """Test GitStatusChecker class"""

    def test_non_git_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            result = statusline.GitStatusChecker.check_dirty_status(temp_dir)
            self.assertFalse(result)

    def test_cache_behavior(self):
        statusline.GitStatusChecker._cache.clear()
        with tempfile.TemporaryDirectory() as temp_dir:
            result1 = statusline.GitStatusChecker.check_dirty_status(temp_dir)
            result2 = statusline.GitStatusChecker.check_dirty_status(temp_dir)
            self.assertEqual(result1, result2)
            self.assertIn(temp_dir, statusline.GitStatusChecker._cache)


class TestCrossPlatformLocking(unittest.TestCase):
    """Test cross-platform file locking functions"""

    def test_flock_and_funlock(self):
        """Test that flock/funlock work without errors"""
        with tempfile.NamedTemporaryFile(mode='w') as f:
            # Should not raise
            statusline._flock(f, exclusive=True)
            statusline._funlock(f)

    def test_flock_shared(self):
        """Test shared lock"""
        with tempfile.NamedTemporaryFile(mode='w') as f:
            statusline._flock(f, exclusive=False)
            statusline._funlock(f)


class TestLoggingSetup(unittest.TestCase):
    """Test logging setup functions"""

    def test_should_run_cleanup_first_time(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            result = statusline._should_run_log_cleanup(Path(temp_dir))
            self.assertTrue(result)

    def test_cleanup_marker(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir)
            statusline._mark_cleanup_done(log_dir)
            marker = log_dir / '.last_cleanup'
            self.assertTrue(marker.exists())


class TestMainIntegration(unittest.TestCase):
    """Integration tests for main function"""

    @patch('sys.stdout', new_callable=StringIO)
    def test_full_output_with_all_features(self, mock_stdout):
        """Test full output with context window, vim mode, etc."""
        mock_input = json.dumps({
            'model': {'display_name': 'Sonnet 4.5'},
            'workspace': {'current_dir': '/tmp'},
            'cost': {
                'total_cost_usd': 0.125,
                'total_duration_ms': 300000,
                'total_lines_added': 127,
                'total_lines_removed': 43,
                'total_api_duration_ms': 5000
            },
            'context_window': {
                'used_percentage': 42,
                'total_input_tokens': 45000,
                'total_output_tokens': 12000
            },
            'vim': {'mode': 'normal'},
            'output_style': {'name': 'concise'}
        })

        with patch('sys.stdin', StringIO(mock_input)):
            with patch.dict(os.environ, {}, clear=False):
                statusline.main()

        output = mock_stdout.getvalue()
        self.assertIn('Sonnet 4.5', output)
        self.assertIn('ctx:42%', output)
        self.assertIn('[N]', output)
        self.assertIn('concise', output)
        self.assertIn('+127/-43', output)

    @patch('sys.stdout', new_callable=StringIO)
    def test_output_without_optional_fields(self, mock_stdout):
        """Test output when optional fields are missing"""
        mock_input = json.dumps({
            'model': {'display_name': 'Claude'},
            'workspace': {'current_dir': '/tmp'}
        })

        with patch('sys.stdin', StringIO(mock_input)):
            statusline.main()

        output = mock_stdout.getvalue()
        self.assertIn('Claude', output)
        self.assertNotIn('ctx:', output)
        self.assertNotIn('[N]', output)


if __name__ == '__main__':
    unittest.main()
