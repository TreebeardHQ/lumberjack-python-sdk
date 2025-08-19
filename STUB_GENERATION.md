# Type Stub Generation Guide

This project uses auto-generated type stub files (`.pyi`) to provide excellent IDE support and type checking.

## Overview

- **Source**: Stub files are generated using `mypy stubgen`
- **Location**: All `.pyi` files are in `src/lumberjack_sdk/`
- **Distribution**: Included in package builds via `pyproject.toml`
- **py.typed**: Package is marked as typed with `src/lumberjack_sdk/py.typed`

## Generating Stubs

### Automatic (Recommended)
```bash
python generate_stubs.py
```

This script:
1. Generates fresh stub files using `mypy stubgen`
2. Copies them to the `src/` directory
3. **Automatically applies manual enhancements** to preserve IDE support
4. Cleans up temporary files

### Manual
```bash
stubgen -p lumberjack_sdk -o .
cp -r lumberjack_sdk/*.pyi src/lumberjack_sdk/
rm -rf lumberjack_sdk/
```

⚠️ **Warning**: Manual generation will lose enhancements. Use the script instead.

## Manual Enhancements

The `generate_stubs.py` script automatically applies these enhancements:

### `core.pyi` - Lumberjack.init() Method
- **Problem**: `stubgen` generates `init(cls, **kwargs: Any)` which hides parameters from IDE
- **Solution**: Replaces with explicit parameter signature matching `__init__()`
- **Result**: IDE shows all 23+ parameters with types and defaults

## IDE Benefits

✅ **Parameter hovering**: Detailed descriptions for all parameters  
✅ **Autocomplete**: Full parameter suggestions with types  
✅ **Type checking**: Real-time validation with mypy  
✅ **Import intelligence**: Better autocomplete for exports  

## Package Distribution

Stub files are automatically included in package builds:

```toml
# pyproject.toml
[tool.hatch.build.targets.wheel]
include = [
    "src/lumberjack_sdk/py.typed",
    "src/lumberjack_sdk/**/*.pyi",
]
```

## Development Workflow

### Manual Generation
1. **After code changes**: Run `python generate_stubs.py`
2. **Before releases**: Ensure stubs are up to date
3. **Testing**: Use `test_ide_support.py` to verify IDE functionality

### Automatic Generation
- **During releases**: `python push.py` automatically generates stubs before building
- **CI/CD**: Consider adding stub generation to your build pipeline
- **Pre-commit**: You can add stub generation as a pre-commit hook

### Build Integration

Stub generation is **NOT** automatic during regular builds to avoid:
- Build dependencies on mypy/stubgen
- Potential build failures in CI environments
- Unnecessary regeneration during development

Instead:
- Use `python generate_stubs.py` manually when needed
- Release script (`push.py`) automatically generates stubs
- Stub files are committed to git for consistency

## Troubleshooting

### IDE not showing parameter hints
1. Ensure stub files are present: `ls src/lumberjack_sdk/*.pyi`
2. Check `py.typed` marker exists: `ls src/lumberjack_sdk/py.typed`  
3. Restart your IDE/language server
4. Verify package installation includes stubs

### Type checking errors
1. Run `mypy test_ide_support.py` to test
2. Regenerate stubs: `python generate_stubs.py`
3. Check for syntax errors in `.pyi` files

### Stubs out of sync
1. Always use `python generate_stubs.py` instead of manual commands
2. The script preserves manual enhancements automatically
3. Check git diff to see what changed