# run all clean tasks
[group('clean')]
clean: clean-build clean-cache clean-constraints clean-coverage clean-ty clean-pytest clean-python clean-requirements clean-ruff

# clean build folders
[group('clean')]
clean-build:
    uv run python -c "import shutil; [shutil.rmtree(d, ignore_errors=True) for d in ['dist', 'build']]"

# clean cache folder
[group('clean')]
clean-cache:
    uv run python -c "import shutil; shutil.rmtree('.cache', ignore_errors=True)"

# clean constraints file
[group('clean')]
clean-constraints:
    uv run python -c "import pathlib; pathlib.Path('constraints.txt').unlink(missing_ok=True)"

# clean coverage files
[group('clean')]
clean-coverage:
    uv run python -c "import pathlib; [p.unlink() for p in pathlib.Path('.').glob('.coverage*') if p.is_file()]"

# clean ty cache
[group('clean')]
clean-ty:
    uv run python -c "import shutil; shutil.rmtree('.ty_cache', ignore_errors=True)"

# clean pytest cache
[group('clean')]
clean-pytest:
    uv run python -c "import shutil; shutil.rmtree('.pytest_cache', ignore_errors=True)"

# clean python caches (__pycache__ and .pyc/.pyo files)
[group('clean')]
clean-python:
    uv run python -c "import pathlib, shutil; [shutil.rmtree(str(d)) for d in pathlib.Path('.').rglob('__pycache__') if d.is_dir()]"
    uv run python -c "import pathlib; [p.unlink() for p in pathlib.Path('.').rglob('*.py[co]')]"

# clean requirements file
[group('clean')]
clean-requirements:
    uv run python -c "import pathlib; pathlib.Path('requirements.txt').unlink(missing_ok=True)"

# clean ruff cache
[group('clean')]
clean-ruff:
    uv run python -c "import shutil; shutil.rmtree('.ruff_cache', ignore_errors=True)"

# clean venv folder
[confirm]
[group('clean')]
clean-venv:
    uv run python -c "import shutil; shutil.rmtree('.venv', ignore_errors=True)"
