import subprocess


def snapshot(cwd: str, timeout: float = 3.0, max_bytes: int = 1_000_000):
    result = {"is_git": False, "warnings": []}
    try:
        subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--git-dir"],
            check=True,
            capture_output=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        result["warnings"].append("not a git repository or git unavailable")
        return result
    result["is_git"] = True
    for name, args in {
        "branch": ["branch", "--show-current"],
        "head": ["rev-parse", "HEAD"],
        "status": ["status", "--short"],
        "diff": ["diff", "--stat"],
    }.items():
        try:
            p = subprocess.run(
                ["git", "-C", cwd, *args],
                capture_output=True,
                timeout=timeout,
                check=False,
            )
            result[name] = p.stdout[:max_bytes].decode("utf-8", errors="replace")
        except (OSError, subprocess.SubprocessError) as e:
            result["warnings"].append(f"{name}: {e}")
    return result
