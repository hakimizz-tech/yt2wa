"""Architecture rules, checked by reading the source (no imports run)."""

import ast
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src" / "yt2wa"
LAYERS = ("domain", "application", "infrastructure", "interface", "bootstrap")

# Layer -> layers it must never import.
FORBIDDEN = {
    "domain": {"application", "infrastructure", "interface", "bootstrap"},
    "application": {"infrastructure", "interface", "bootstrap"},
    "infrastructure": {"application", "interface", "bootstrap"},
    "bootstrap": {"interface"},
}
THIRD_PARTY_FREE = ("domain", "application")
LAZY_LIBRARIES = {"yt_dlp", "ytmusicapi"}


def modules(layer):
    return sorted((SRC / layer).rglob("*.py"))


def imported_names(tree, top_level_only=False):
    """Yield (module name, is_top_level) for every import."""
    for node in ast.walk(tree):
        top = node in tree.body
        if top_level_only and not top:
            continue
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif (
            isinstance(node, ast.ImportFrom)
            and node.level == 0
            and node.module
        ):
            yield node.module


def parse(path):
    return ast.parse(path.read_text(encoding="utf-8"))


def all_files():
    return [(layer, path) for layer in LAYERS for path in modules(layer)]


@pytest.mark.parametrize(
    ("layer", "path"), all_files(), ids=lambda v: getattr(v, "name", v)
)
def test_layers_only_import_inward(layer, path):
    for name in imported_names(parse(path)):
        parts = name.split(".")
        if parts[0] == "yt2wa" and len(parts) > 1:
            target = parts[1]
            assert target not in FORBIDDEN.get(layer, set()), (
                f"{path.relative_to(SRC)} imports {name}"
            )


@pytest.mark.parametrize(
    "path",
    [p for layer in THIRD_PARTY_FREE for p in modules(layer)],
    ids=lambda p: str(p.relative_to(SRC)),
)
def test_domain_and_application_use_only_the_standard_library(path):
    for name in imported_names(parse(path)):
        root = name.split(".")[0]
        assert root == "yt2wa" or root in sys.stdlib_module_names, (
            f"{path.relative_to(SRC)} imports third-party module {name}"
        )


@pytest.mark.parametrize(
    "path",
    [p for layer in ("infrastructure", "bootstrap") for p in modules(layer)],
    ids=lambda p: str(p.relative_to(SRC)),
)
def test_optional_libraries_are_only_imported_lazily(path):
    for name in imported_names(parse(path), top_level_only=True):
        assert name.split(".")[0] not in LAZY_LIBRARIES, (
            f"{path.relative_to(SRC)} imports {name} at module level"
        )


def test_every_layer_has_modules():
    for layer in LAYERS:
        assert modules(layer), layer


def test_ports_are_protocols_and_adapters_do_not_inherit_from_them():
    tree = parse(SRC / "domain" / "ports.py")
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            bases = {
                getattr(b, "id", getattr(b, "attr", "")) for b in node.bases
            }
            assert "Protocol" in bases, node.name


def test_search_providers_follow_the_port():
    from yt2wa.domain.ports import SearchProvider
    from yt2wa.infrastructure.ytdlp_search import YtDlpSearchProvider
    from yt2wa.infrastructure.ytmusicapi_search import YtMusicApiSearchProvider

    wanted = list(SearchProvider.search.__annotations__)
    import inspect

    for adapter in (YtDlpSearchProvider, YtMusicApiSearchProvider):
        got = list(inspect.signature(adapter.search).parameters)
        assert got[1:4] == ["query", "kind", "limit"], adapter
    assert "return" in wanted
