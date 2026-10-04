import ast
from pathlib import Path

def test_engine_purity():
    """Verify that engine code only imports allowed standard library modules."""
    engine_dir = Path(__file__).parent.parent / "stretch" / "engine"
    
    allowed_modules = {
        "datetime",
        "math",
        "dataclasses",
        "typing",
        "enum",
        "functools",
        "calendar",
        "__future__",
    }
    
    # Also allow relative imports within the engine
    allowed_internal_prefixes = ["stretch.engine."]
    
    for py_file in engine_dir.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    base_module = alias.name.split('.')[0]
                    assert base_module in allowed_modules, f"Disallowed import {alias.name} in {py_file.name}"
            
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    is_internal = any(node.module.startswith(p) for p in allowed_internal_prefixes)
                    if not is_internal and node.level == 0:  # level 0 means absolute import
                        base_module = node.module.split('.')[0]
                        assert base_module in allowed_modules, f"Disallowed import from {node.module} in {py_file.name}"
                    
                    if node.level > 0: # relative imports are internal
                        pass
