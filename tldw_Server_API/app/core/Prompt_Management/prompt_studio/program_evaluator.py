"""
program_evaluator.py
Sandboxed Program Evaluator (Phase 2)

Executes extracted Python code in a restricted subprocess with resource limits
and evaluates objective/constraints to produce a reward in [-1..10].

Notes:
- Network and filesystem access are blocked via static checks and isolated mode.
- Per-project feature toggle is supported via project metadata or env var.
"""

import os
import re
import sys
import json
import tempfile
import subprocess
import textwrap
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, List


_FORBIDDEN_IMPORTS = {
    "socket", "requests", "urllib", "http", "ftplib", "subprocess", "multiprocessing", "asyncio",
    "ssl", "paramiko", "pandas_datareader", "psutil", "sqlite3", "pymongo", "boto3", "smtplib",
}
_FORBIDDEN_PATTERNS = [
    r"\bos\.system\(", r"\bsubprocess\.", r"\bopen\(", r"\burllib\.", r"\brequests\.", r"\bsocket\.",
]


@dataclass
class EvalResult:
    success: bool
    reward: float
    metrics: Dict[str, Any]
    error: Optional[str] = None


class ProgramEvaluator:
    """Sandboxed evaluator for python code in Prompt Studio (Phase 2).

    Usage:
      - feature toggle via env PROMPT_STUDIO_ENABLE_CODE_EVAL or project metadata
      - extract code from LLM output (``` fences preferred)
      - execute under resource limits and isolated mode
      - evaluate objective/constraints from test case spec or stdout JSON
    """

    # Default execution limits
    CPU_TIME_SEC = 4
    WALL_TIME_SEC = 8
    MEMORY_MB = 256

    @staticmethod
    def is_enabled_globally() -> bool:
        return str(os.getenv("PROMPT_STUDIO_ENABLE_CODE_EVAL", "false")).strip().lower() in {"1", "true", "yes"}

    @staticmethod
    def is_enabled_for_project(db, project_id: Optional[int]) -> bool:
        if project_id is None:
            return ProgramEvaluator.is_enabled_globally()
        try:
            proj = db.get_project(project_id)
            md = proj.get("metadata") if isinstance(proj, dict) else None
            if isinstance(md, str):
                try:
                    md = json.loads(md)
                except Exception:
                    md = None
            if isinstance(md, dict):
                flag = md.get("enable_code_eval")
                if isinstance(flag, bool):
                    return flag
        except Exception:
            pass
        return ProgramEvaluator.is_enabled_globally()

    # --------------------------------------------------------------------------------------------
    # Public API
    # --------------------------------------------------------------------------------------------
    def evaluate_text_output(self, text: str) -> float:
        """Fallback heuristic reward if sandbox execution is disabled.

        Returns a reward in [-1..10].
        """
        if not text:
            return -1.0
        t = text.lower()
        reward = 0.0
        if "def " in t or "class " in t:
            reward += 3.0
        if "import " in t:
            reward += 1.5
        if "if __name__ == '__main__'" in t or "if __name__ == \"__main__\"" in t:
            reward += 1.0
        for lib in ("numpy", "pandas", "cvxpy", "scipy"):
            if f"import {lib}" in t:
                reward += 0.5
        if any(re.search(p, text) for p in _FORBIDDEN_PATTERNS):
            reward -= 2.0
        return float(max(-1.0, min(10.0, reward)))

    def evaluate(self, *, project_id: Optional[int], db, llm_output: str, spec: Optional[Dict[str, Any]] = None) -> EvalResult:
        """End-to-end evaluation: extract code, run sandbox, score.

        spec may include:
          - objective: "minimize" | "maximize"
          - metric_var: variable name in code globals to inspect (float)
          - constraints: list of simple expressions using names from code globals
        """
        if not self.is_enabled_for_project(db, project_id):
            # Feature disabled → fallback heuristic
            return EvalResult(True, self.evaluate_text_output(llm_output), metrics={"mode": "heuristic"})

        code = self._extract_code(llm_output)
        if not code:
            return EvalResult(False, -1.0, metrics={}, error="No code detected in output")

        # Quick static security scan
        if self._has_forbidden_constructs(code):
            return EvalResult(False, -1.0, metrics={}, error="Forbidden imports or calls detected")

        success, exec_out, exec_err, globals_dump = self._execute_in_sandbox(code)
        if not success:
            return EvalResult(False, -1.0, metrics={"stderr": exec_err, "stdout": exec_out}, error="Execution failed")

        reward, metrics = self._score_from_outputs(exec_out, globals_dump, spec or {})
        return EvalResult(True, reward, metrics)

    # --------------------------------------------------------------------------------------------
    # Internals
    # --------------------------------------------------------------------------------------------
    def _extract_code(self, text: str) -> Optional[str]:
        """Extract python code from fenced blocks or heuristics."""
        if not text:
            return None
        # Prefer fenced blocks
        m = re.findall(r"```(?:python)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
        if m:
            # Pick the largest block and normalize indentation
            block = max(m, key=lambda s: len(s))
            return textwrap.dedent(block).strip()
        # Heuristic: find regions with many code-like lines
        lines = text.splitlines()
        buf: List[str] = []
        for ln in lines:
            if any(tok in ln for tok in ("def ", "import ", "class ", "return ", "for ", "while ")):
                buf.append(ln)
        code = "\n".join(buf).strip()
        return code or None

    def _has_forbidden_constructs(self, code: str) -> bool:
        for name in _FORBIDDEN_IMPORTS:
            if re.search(rf"\bimport\s+{re.escape(name)}\b", code):
                return True
        for pat in _FORBIDDEN_PATTERNS:
            if re.search(pat, code):
                return True
        return False

    def _execute_in_sandbox(self, code: str) -> Tuple[bool, str, str, Dict[str, Any]]:
        """Execute code in a restricted subprocess using isolated mode.

        Returns (success, stdout, stderr, globals_dump)
        """
        cpu_lim = int(self.CPU_TIME_SEC)
        mem_lim = int(self.MEMORY_MB) * 1024 * 1024
        forbidden_json = json.dumps(sorted(list(_FORBIDDEN_IMPORTS)))
        code_json = json.dumps(code)
        wrapper_lines = [
            "import sys, json, builtins",
            "# Try to set resource limits (best-effort)",
            "try:",
            "    import resource",
            f"    resource.setrlimit(resource.RLIMIT_CPU, ({cpu_lim}, {cpu_lim}))",
            f"    resource.setrlimit(resource.RLIMIT_AS, ({mem_lim}, {mem_lim}))",
            "except Exception:",
            "    pass",
            "",
            "# Best-effort isolation: disable file I/O via builtins.open",
            "def _blocked(*a, **k):",
            "    raise RuntimeError(\"file/network operations are disabled\")",
            "for name in (\"open\",):",
            "    setattr(builtins, name, _blocked)",
            "",
            "# Guarded import to block dangerous modules",
            f"_forbidden = {forbidden_json}",
            "_orig_import = builtins.__import__",
            "def _guarded_import(name, globals=None, locals=None, fromlist=(), level=0):",
            "    base = name.split('.')[0]",
            "    if base in _forbidden:",
            "        raise ImportError(f\"Forbidden import: {name}\")",
            "    return _orig_import(name, globals, locals, fromlist, level)",
            "builtins.__import__ = _guarded_import",
            "",
            "# Execute user code",
            "__code_globals = {}",
            "__code_locals = None",
            # Embed the pre-JSON-encoded string as a safe Python literal
            # Using !r ensures backslashes (e.g., \n) remain escaped for json.loads
            f"__user_code = json.loads({code_json!r})",
            "try:",
            "    # First try to execute as-is",
            "    exec(compile(__user_code, '<sandbox>', 'exec'), __code_globals, __code_locals)",
            "except IndentationError:",
            "    # Fallback: normalize leading indentation per line and retry",
            "    __user_code_fixed = '\\n'.join(line.lstrip() for line in __user_code.splitlines())",
            "    try:",
            "        exec(compile(__user_code_fixed, '<sandbox>', 'exec'), __code_globals, __code_locals)",
            "    except Exception as e2:",
            "        print(f\"__EXEC_ERROR__: {e2}\", file=sys.stderr)",
            "        sys.exit(7)",
            "except Exception as e:",
            "    print(f\"__EXEC_ERROR__: {e}\", file=sys.stderr)",
            "    sys.exit(7)",
            "",
            "# Serialize selected globals back to parent via stdout trailer",
            "def _jsonable(v):",
            "    import math",
            "    if isinstance(v, (int, float, str, bool)) or v is None:",
            "        return True",
            "    if isinstance(v, (list, tuple)):",
            "        return all(_jsonable(x) for x in v[:50])",
            "    if isinstance(v, dict):",
            "        return all(isinstance(k, str) and _jsonable(v[k]) for k in list(v.keys())[:50])",
            "    return False",
            "_dump = {}",
            "for k, v in list(__code_globals.items()):",
            "    if k.startswith('__'):",
            "        continue",
            "    if _jsonable(v):",
            "        _dump[k] = v",
            "print('\\n__GLOBALS_JSON__\\n' + json.dumps(_dump, separators=(',',':')))",
        ]
        wrapper = "\n".join(wrapper_lines)
        # Create temp dir and files
        with tempfile.TemporaryDirectory() as td:
            script_path = os.path.join(td, "sandbox_runner.py")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(wrapper)
            # Run isolated Python: -I ignores env vars/user site; -B no pyc; no cwd files
            env = {"PYTHONHASHSEED": "0"}
            try:
                proc = subprocess.run(
                    [sys.executable, "-I", "-B", script_path],
                    cwd=td,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=self.WALL_TIME_SEC,
                )
            except subprocess.TimeoutExpired as te:
                return False, te.stdout or "", te.stderr or "timeout", {}
            out, err = proc.stdout or "", proc.stderr or ""
            if proc.returncode != 0:
                return False, out, err, {}
            # Extract globals JSON trailer
            gjson = {}
            if "__GLOBALS_JSON__" in out:
                try:
                    tail = out.split("__GLOBALS_JSON__", 1)[1]
                    gjson = json.loads(tail.strip())
                except Exception:
                    gjson = {}
            return True, out, err, gjson

    def _score_from_outputs(self, stdout: str, globals_dump: Dict[str, Any], spec: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
        """Map execution results to reward in [-1..10]."""
        metrics: Dict[str, Any] = {"mode": "sandbox", "constraints_ok": None}

        # If spec provides metric_var and objective, use it
        metric_var = (spec or {}).get("metric_var")
        objective = str((spec or {}).get("objective", "maximize")).lower()
        constraints = (spec or {}).get("constraints") or []

        score_val: Optional[float] = None
        if metric_var and isinstance(globals_dump, dict) and metric_var in globals_dump:
            try:
                score_val = float(globals_dump[metric_var])
                metrics["metric_var_value"] = score_val
            except Exception:
                score_val = None

        # If not found, try to parse last float from stdout
        if score_val is None and stdout:
            nums = re.findall(r"[-+]?[0-9]*\.?[0-9]+", stdout)
            if nums:
                try:
                    score_val = float(nums[-1])
                    metrics["parsed_metric_value"] = score_val
                except Exception:
                    pass

        # Evaluate simple constraints: expect expressions like "x >= 0" over globals_dump
        constraints_ok = True
        if constraints and isinstance(globals_dump, dict):
            for expr in constraints:
                if not self._safe_eval_constraint(expr, globals_dump):
                    constraints_ok = False
                    break
        metrics["constraints_ok"] = constraints_ok

        # Map to reward: if no metric was found, give small heuristic
        if score_val is None:
            base = 3.0 if "success" in (stdout or "").lower() else 1.0
            return float(max(-1.0, min(10.0, base - (0 if constraints_ok else 1.5)))), metrics

        # Normalize: if objective is minimize, invert
        # We map into [0..10] based on relative magnitude; absent a scale, use a soft mapping
        val = float(score_val)
        if objective.startswith("min"):
            # Smaller is better; transform to higher reward when closer to 0
            reward = 10.0 / (1.0 + max(0.0, val))
        else:
            # Larger is better; saturating growth
            reward = 10.0 * (1.0 - (1.0 / (1.0 + max(0.0, val))))
        if not constraints_ok:
            reward *= 0.5
        return float(max(-1.0, min(10.0, reward))), metrics

    # --------------------------------------------------------------------------------------------
    # Safe constraint evaluation via AST
    def _safe_eval_constraint(self, expr: str, names: Dict[str, Any]) -> bool:
        import ast
        try:
            tree = ast.parse(str(expr), mode="eval")
        except Exception:
            return False

        allowed_nodes = (
            ast.Expression, ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare,
            ast.Name, ast.Load, ast.Constant, ast.Num,
            ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.Pow,
            ast.And, ast.Or, ast.Not,
            ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
            ast.USub, ast.UAdd,
        )

        for node in ast.walk(tree):
            if not isinstance(node, allowed_nodes):
                return False
        try:
            env = {k: names.get(k) for k in names.keys()}
            return bool(eval(compile(tree, "<constraint>", "eval"), {"__builtins__": {}}, env))
        except Exception:
            return False
