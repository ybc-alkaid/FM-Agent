from dataclasses import dataclass
from typing import Callable

from src.languages import python as _python


@dataclass
class LanguageHandler:
    """Extraction and call-graph backend for one language.

    batch_extract(cg, proj_dir) -> {abs_filepath: [(func_name, body)]}
    call_edges(cg)              -> {(caller_stem, caller_basename): {callee_stems}}

    To add a new language:
      1. Create src/languages/<lang>.py implementing batch_extract and call_edges
      2. Import it here and add one entry to REGISTRY
    No other files need to change.
    """
    batch_extract: Callable
    call_edges: Callable


REGISTRY: dict = {
    "python": LanguageHandler(
        batch_extract=_python.batch_extract,
        call_edges=_python.call_edges,
    ),
}
