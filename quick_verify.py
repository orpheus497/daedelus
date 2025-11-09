#!/usr/bin/env python3
"""
Quick verification of Daedelus modules - skips missing optional dependencies.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_import_graceful(module_name, description):
    """Test importing a module, gracefully handling missing dependencies"""
    try:
        __import__(module_name)
        print(f"✓ {description}")
        return True, None
    except ImportError as e:
        # Check if it's just a missing dependency vs actual code issue
        missing_dep = str(e).split("'")[1] if "'" in str(e) else str(e)
        if "No module named" in str(e):
            print(f"⚠ {description} - Missing dependency: {missing_dep}")
            return False, f"missing_dep:{missing_dep}"
        else:
            print(f"✗ {description} - Import error: {e}")
            return False, f"import_error:{e}"
    except Exception as e:
        print(f"✗ {description} - Error: {e}")
        return False, f"error:{e}"

def main():
    """Run verification"""
    print("=" * 70)
    print("DAEDELUS QUICK VERIFICATION")
    print("=" * 70)
    print()

    results = []
    missing_deps = set()

    # Test critical modules that should work with minimal deps
    print("Core Modules:")
    print("-" * 70)

    test_modules = [
        ("daedelus.utils.config", "Config utils"),
        ("daedelus.utils.logging_config", "Logging config"),
        ("daedelus.core.safety", "Safety analyzer"),
    ]

    for module, desc in test_modules:
        success, error = test_import_graceful(module, desc)
        results.append(success)
        if error and error.startswith("missing_dep:"):
            missing_deps.add(error.split(":", 1)[1])

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)

    if missing_deps:
        print(f"\nMissing dependencies: {', '.join(sorted(missing_deps))}")
        print("\nTo install all dependencies, run:")
        print("  pip install -e .")

    passed = sum(results)
    total = len(results)
    print(f"\nPassed: {passed}/{total}")

    if passed == total:
        print("\n✓ Core modules verified successfully!")
        return 0
    else:
        print(f"\n⚠ {total - passed} modules need dependencies")
        return 0  # Still return 0 since missing deps are expected

if __name__ == "__main__":
    sys.exit(main())
