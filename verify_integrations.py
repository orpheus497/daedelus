#!/usr/bin/env python3
"""
Comprehensive verification script for all Daedelus integrations and features.
Tests imports, basic functionality, and integration points.

Author: orpheus497
"""

import sys
import traceback
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_import(module_name, description):
    """Test importing a module"""
    try:
        __import__(module_name)
        print(f"✓ {description}: {module_name}")
        return True
    except Exception as e:
        print(f"✗ {description}: {module_name}")
        print(f"  Error: {e}")
        traceback.print_exc()
        return False

def main():
    """Run all verification tests"""
    print("=" * 70)
    print("DAEDELUS INTEGRATION VERIFICATION")
    print("=" * 70)

    results = []

    # Core modules
    print("\n1. Core Modules")
    print("-" * 70)
    results.append(test_import("daedelus.core.database", "Database module"))
    results.append(test_import("daedelus.core.embeddings", "Embeddings module"))
    results.append(test_import("daedelus.core.vector_store", "Vector store module"))
    results.append(test_import("daedelus.core.suggestions", "Suggestions module"))
    results.append(test_import("daedelus.core.safety", "Safety module"))
    results.append(test_import("daedelus.core.templates", "Templates module"))
    results.append(test_import("daedelus.core.file_operations", "File operations"))
    results.append(test_import("daedelus.core.command_executor", "Command executor"))
    results.append(test_import("daedelus.core.tool_system", "Tool system"))
    results.append(test_import("daedelus.core.integration", "Integration module"))

    # LLM modules
    print("\n2. LLM Modules")
    print("-" * 70)
    results.append(test_import("daedelus.llm.llm_manager", "LLM manager"))
    results.append(test_import("daedelus.llm.command_generator", "Command generator"))
    results.append(test_import("daedelus.llm.command_explainer", "Command explainer"))
    results.append(test_import("daedelus.llm.rag_pipeline", "RAG pipeline"))
    results.append(test_import("daedelus.llm.enhanced_suggestions", "Enhanced suggestions"))
    results.append(test_import("daedelus.llm.web_search", "Web search"))
    results.append(test_import("daedelus.llm.document_ingestion", "Document ingestion"))
    results.append(test_import("daedelus.llm.semantic_chunker", "Semantic chunker"))
    results.append(test_import("daedelus.llm.model_manager", "Model manager"))
    results.append(test_import("daedelus.llm.deus_model_manager", "Deus model manager"))
    results.append(test_import("daedelus.llm.peft_trainer", "PEFT trainer"))
    results.append(test_import("daedelus.llm.training_coordinator", "Training coordinator"))
    results.append(test_import("daedelus.llm.training_data_organizer", "Training data organizer"))
    results.append(test_import("daedelus.llm.training_ui", "Training UI"))
    results.append(test_import("daedelus.llm.model_downloader", "Model downloader"))

    # CLI modules
    print("\n3. CLI Modules")
    print("-" * 70)
    results.append(test_import("daedelus.cli.main", "CLI main"))
    results.append(test_import("daedelus.cli.repl", "REPL"))
    results.append(test_import("daedelus.cli.extended_commands", "Extended commands"))

    # Daemon modules
    print("\n4. Daemon Modules")
    print("-" * 70)
    results.append(test_import("daedelus.daemon.daemon", "Daemon"))
    results.append(test_import("daedelus.daemon.ipc", "IPC"))

    # UI modules
    print("\n5. UI Modules")
    print("-" * 70)
    results.append(test_import("daedelus.ui.dashboard", "Dashboard"))
    results.append(test_import("daedelus.ui.enhanced_dashboard", "Enhanced dashboard"))
    results.append(test_import("daedelus.ui.settings_panel", "Settings panel"))
    results.append(test_import("daedelus.ui.memory_and_permissions", "Memory & permissions"))

    # Utils modules
    print("\n6. Utils Modules")
    print("-" * 70)
    results.append(test_import("daedelus.utils.config", "Config"))
    results.append(test_import("daedelus.utils.logging_config", "Logging config"))
    results.append(test_import("daedelus.utils.backup", "Backup"))
    results.append(test_import("daedelus.utils.fuzzy", "Fuzzy matching"))
    results.append(test_import("daedelus.utils.dependencies", "Dependencies"))
    results.append(test_import("daedelus.utils.highlighting", "Highlighting"))

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    total = len(results)
    passed = sum(results)
    failed = total - passed

    print(f"Total tests: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Success rate: {passed/total*100:.1f}%")

    if failed > 0:
        print("\n⚠️  Some modules failed to import!")
        return 1
    else:
        print("\n✓ All modules imported successfully!")
        return 0

if __name__ == "__main__":
    sys.exit(main())
