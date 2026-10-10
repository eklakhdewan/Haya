"""Tests for Static AST Security Checker and policy rules."""

from orchestrator.sandbox.static_checker import StaticSecurityChecker


def test_safe_code_passes() -> None:
    code = """
def fibonacci(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a

print(fibonacci(10))
"""
    result = StaticSecurityChecker.check(code, network="disabled")
    assert result.passed is True
    assert len(result.violations) == 0


def test_prohibited_subprocess_import_blocked() -> None:
    code = """
import subprocess
subprocess.run(['ls', '-la'])
"""
    result = StaticSecurityChecker.check(code, network="disabled")
    assert result.passed is False
    assert any("Prohibited import detected: 'subprocess'" in v for v in result.violations)


def test_prohibited_os_system_call_blocked() -> None:
    code = """
import os
os.system('cat /etc/passwd')
"""
    result = StaticSecurityChecker.check(code, network="disabled")
    assert result.passed is False
    assert any("Dangerous system call detected: 'os.system'" in v for v in result.violations)


def test_network_import_blocked_when_disabled() -> None:
    code = """
import urllib.request
response = urllib.request.urlopen('http://example.com')
"""
    result = StaticSecurityChecker.check(code, network="disabled")
    assert result.passed is False
    assert any("Network import prohibited while network is disabled" in v for v in result.violations)

    # When network is enabled, urllib should not be blocked by the network rule
    result_enabled = StaticSecurityChecker.check(code, network="enabled")
    assert not any("Network import prohibited" in v for v in result_enabled.violations)


def test_sensitive_credentials_string_blocked() -> None:
    code = """
with open('.env', 'r') as f:
    secrets = f.read()
"""
    result = StaticSecurityChecker.check(code, network="disabled")
    assert result.passed is False
    assert any("Access to sensitive resource/credential detected: '.env'" in v for v in result.violations)


def test_syntax_error_handled_gracefully() -> None:
    code = "def broken_code(: print('invalid')"
    result = StaticSecurityChecker.check(code, network="disabled")
    assert result.passed is False
    assert any("Syntax error" in v for v in result.violations)
