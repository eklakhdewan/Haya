"""Static AST security and policy verification for generated code."""

import ast
from dataclasses import dataclass, field


@dataclass
class StaticCheckResult:
    passed: bool
    violations: list[str] = field(default_factory=list)


class StaticSecurityChecker:
    """Performs static syntax and AST analysis to enforce code isolation policies before execution."""

    ALWAYS_PROHIBITED_MODULES = {
        "subprocess",
        "pty",
        "posix",
        "pwd",
        "spwd",
        "grp",
        "crypt",
        "winreg",
        "ctypes",
    }

    NETWORK_MODULES = {
        "socket",
        "urllib",
        "requests",
        "httpx",
        "aiohttp",
        "ftplib",
        "telnetlib",
        "paramiko",
        "http.client",
    }

    DANGEROUS_ATTRIBUTES = {
        ("os", "system"),
        ("os", "popen"),
        ("os", "exec"),
        ("os", "execl"),
        ("os", "execle"),
        ("os", "execlp"),
        ("os", "execv"),
        ("os", "execve"),
        ("os", "execvp"),
        ("os", "spawn"),
        ("shutil", "rmtree"),
    }

    SENSITIVE_STRING_PATTERNS = [
        "/etc/shadow",
        "/etc/passwd",
        ".env",
        "id_rsa",
        "aws_secret_access_key",
        "google_api_key",
    ]

    MAX_CODE_CHARS = 50_000

    @classmethod
    def check(cls, code: str, network: str = "disabled") -> StaticCheckResult:
        violations: list[str] = []

        if len(code) > cls.MAX_CODE_CHARS:
            violations.append(
                f"Code length ({len(code)} chars) exceeds maximum allowed limit ({cls.MAX_CODE_CHARS} chars)."
            )

        # 1. Parse AST
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            violations.append(f"Syntax error in code: {e}")
            return StaticCheckResult(passed=False, violations=violations)

        # 2. Inspect AST Nodes
        for node in ast.walk(tree):
            # Check import statements
            if isinstance(node, ast.Import):
                for alias in node.names:
                    mod = alias.name.split(".")[0]
                    if mod in cls.ALWAYS_PROHIBITED_MODULES:
                        violations.append(f"Prohibited import detected: '{alias.name}'")
                    if network == "disabled" and (mod in cls.NETWORK_MODULES or alias.name in cls.NETWORK_MODULES):
                        violations.append(f"Network import prohibited while network is disabled: '{alias.name}'")

            elif isinstance(node, ast.ImportFrom):
                mod = (node.module or "").split(".")[0]
                if mod in cls.ALWAYS_PROHIBITED_MODULES:
                    violations.append(f"Prohibited from-import detected: '{node.module}'")
                if network == "disabled" and (mod in cls.NETWORK_MODULES or node.module in cls.NETWORK_MODULES):
                    violations.append(f"Network from-import prohibited while network is disabled: '{node.module}'")

            # Check attribute calls (e.g. os.system)
            elif isinstance(node, ast.Attribute):
                if isinstance(node.value, ast.Name):
                    attr_pair = (node.value.id, node.attr)
                    if attr_pair in cls.DANGEROUS_ATTRIBUTES:
                        violations.append(f"Dangerous system call detected: '{node.value.id}.{node.attr}'")

            # Check string literals for sensitive file references
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                val_lower = node.value.lower()
                for sensitive in cls.SENSITIVE_STRING_PATTERNS:
                    if sensitive in val_lower:
                        violations.append(f"Access to sensitive resource/credential detected: '{sensitive}'")

        return StaticCheckResult(passed=(len(violations) == 0), violations=violations)
