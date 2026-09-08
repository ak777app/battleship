# Battleship

Single-file Gradio app (`app.py`) with a classic mode and a word-puzzle mode. Run it with `python app.py`
(serves at http://127.0.0.1:7860).

## Tests

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest
```

`pytest` picks up `tests/` and the coverage options from `pyproject.toml` (`--cov=app --cov-report=term-missing`,
failing below 90% coverage). The Gradio `with gr.Blocks(...)` UI construction and the `__main__` launch are
excluded from the coverage report; all game logic in `BattleshipGame` and the module-level handlers is covered.
