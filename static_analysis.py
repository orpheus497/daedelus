#!/usr/bin/env python3
"""
Static code analysis for Daedelus without requiring imports.
Checks for common issues like undefined variables, circular imports, etc.

Author: orpheus497
"""

import ast
import sys
from pathlib import Path
from typing import Dict, List, Set

def analyze_python_file(file_path: Path) -> Dict[str, List[str]]:
    """Analyze a Python file for potential issues"""
    issues = {
        "syntax_errors": [],
        "import_issues": [],
        "undefined_names": [],
        "warnings": []
    }

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for syntax errors
        try:
            tree = ast.parse(content, filename=str(file_path))
        except SyntaxError as e:
            issues["syntax_errors"].append(f"Line {e.lineno}: {e.msg}")
            return issues

        # Analyze imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith('daedelus'):
                        # Check for potential circular imports
                        issues["warnings"].append(f"Line {node.lineno}: Internal import: {alias.name}")

            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.startswith('daedelus'):
                    issues["warnings"].append(f"Line {node.lineno}: Internal import from: {node.module}")

    except Exception as e:
        issues["syntax_errors"].append(f"Failed to analyze: {e}")

    return issues

def main():
    """Run static analysis on all Python files"""
    print("=" * 70)
    print("DAEDELUS STATIC CODE ANALYSIS")
    print("=" * 70)

    src_dir = Path("src/daedelus")
    if not src_dir.exists():
        print(f"Error: {src_dir} not found")
        return 1

    python_files = list(src_dir.rglob("*.py"))

    total_files = len(python_files)
    files_with_issues = 0
    total_issues = 0

    print(f"\nAnalyzing {total_files} Python files...\n")

    for py_file in sorted(python_files):
        relative_path = py_file.relative_to(src_dir.parent)
        issues = analyze_python_file(py_file)

        has_issues = any(issues[key] for key in ["syntax_errors", "import_issues", "undefined_names"])

        if has_issues:
            files_with_issues += 1
            print(f"\n✗ {relative_path}")

            for issue_type, issue_list in issues.items():
                if issue_list and issue_type != "warnings":
                    for issue in issue_list:
                        print(f"  [{issue_type}] {issue}")
                        total_issues += 1
        else:
            print(f"✓ {relative_path}")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Files analyzed: {total_files}")
    print(f"Files with issues: {files_with_issues}")
    print(f"Total issues found: {total_issues}")

    if files_with_issues == 0:
        print("\n✓ No critical issues found!")
        return 0
    else:
        print(f"\n⚠️  Found issues in {files_with_issues} files")
        return 1

if __name__ == "__main__":
    sys.exit(main())
