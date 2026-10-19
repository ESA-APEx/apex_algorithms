"""HTML representations and an optional searchable Jupyter widget."""

from __future__ import annotations

from html import escape
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from esa_apex_toolbox.algorithms import Algorithm


_STYLE = """<style>
.apex-algorithms { color: inherit; font: inherit; line-height: 1.5; max-width: 100%; }
.apex-algorithms * { box-sizing: border-box; }
.apex-algorithms h3 { font-size: 1.15em; margin: 0 0 .25em; }
.apex-algorithms p { margin: .5em 0; }
.apex-algorithms .apex-description { white-space: pre-wrap; overflow-wrap: anywhere; }
.apex-algorithms dl { display: grid; grid-template-columns: minmax(0, 9em) minmax(0, 1fr); gap: .3em 1em; }
.apex-algorithms dt { font-weight: bold; }
.apex-algorithms dd { margin: 0; overflow-wrap: anywhere; }
.apex-algorithms a { color: inherit; text-decoration: underline; }
.apex-algorithms .apex-scroll { max-width: 100%; overflow-x: auto; }
.apex-algorithms table {
    border-collapse: collapse; width: 100%; min-width: 48em; table-layout: fixed; text-align: left;
}
.apex-algorithms th:first-child { width: 40%; }
.apex-algorithms th, .apex-algorithms td { padding: .65em; border-bottom: 1px solid #8c959f; text-align: left; }
.apex-algorithms td { vertical-align: top; overflow-wrap: anywhere; }
.apex-algorithms summary { cursor: pointer; font-weight: bold; overflow-wrap: anywhere; }
.apex-algorithms details[open] summary { margin-bottom: .75em; }
.apex-algorithms .apex-id { font-family: monospace; font-size: .85em; overflow-wrap: anywhere; }
@media (max-width: 480px) {
  .apex-algorithms dl { grid-template-columns: minmax(0, 1fr); gap: .2em; }
  .apex-algorithms dd { margin-bottom: .5em; }
}
</style>"""


def _text(value: str | None) -> str:
    return escape(value) if value else "Not specified"


def _link(href: str, title: str | None) -> str:
    label = _text(title or href)
    try:
        parsed = urlsplit(href)
        safe = parsed.scheme.lower() in {"https", "http"} and bool(parsed.netloc)
    except ValueError:
        safe = False
    if not safe:
        return label
    return f'<a href="{escape(href, quote=True)}" target="_blank" rel="noopener noreferrer">{label}</a>'


def _details(algorithm: Algorithm) -> str:
    services = "<br>".join(_link(link.href, link.title) for link in algorithm.service_links or [])
    process = (
        _link(algorithm.udp_link.href, algorithm.udp_link.title or "openEO process definition")
        if algorithm.udp_link else "Not available"
    )
    fields = [
        ("ID", _text(algorithm.id)),
        ("Provider", _text(algorithm.provider)),
        ("Organization", _text(algorithm.organization)),
        ("Platforms", _text(", ".join(algorithm.platforms))),
        ("Keywords", _text(", ".join(algorithm.keywords))),
        ("License", _text(algorithm.license)),
        ("Services", services or "Not available"),
        ("Process", process),
    ]
    metadata = "".join(f"<dt>{label}</dt><dd>{value}</dd>" for label, value in fields)
    return f'<p class="apex-description">{_text(algorithm.description)}</p><dl>{metadata}</dl>'


def algorithm_html(algorithm: Algorithm) -> str:
    """Render a record without fetching resources or executing catalogue content."""
    return (
        f'{_STYLE}<section class="apex-algorithms" aria-label="Algorithm details">'
        f"<h3>{_text(algorithm.title or algorithm.id)}</h3>{_details(algorithm)}</section>"
    )


def _filter_algorithms(algorithms: list[Algorithm], query: str) -> list[Algorithm]:
    terms = query.casefold().split()
    matches = []
    for algorithm in algorithms:
        text = " ".join([
            algorithm.title or "", algorithm.id, algorithm.provider or "",
            *algorithm.platforms, *algorithm.keywords,
        ]).casefold()
        if all(term in text for term in terms):
            matches.append(algorithm)
    return matches


def algorithm_browser(algorithms: list[Algorithm]):
    """Build a search field and rich results without making network requests."""
    try:
        import ipywidgets as widgets
    except ImportError as error:
        raise ImportError(
            'Searchable displays require ipywidgets. Install the notebook extra: pip install -e ".[notebook]"'
        ) from error

    search = widgets.Text(
        description="Search",
        placeholder="Name, ID, provider, platform or keyword",
        continuous_update=True,
        layout=widgets.Layout(width="100%"),
        style={"description_width": "initial"},
    )
    results = widgets.HTML(value=algorithms_html(algorithms), layout=widgets.Layout(width="100%"))

    def update_results(change):
        results.value = algorithms_html(_filter_algorithms(algorithms, change["new"]))

    search.observe(update_results, names="value")
    return widgets.VBox([search, results], layout=widgets.Layout(width="100%"))


def algorithms_html(algorithms: list[Algorithm]) -> str:
    """Render a catalogue table with locally expandable record details."""
    count = len(algorithms)
    heading = f"{count} algorithm{'s' if count != 1 else ''}"
    if not algorithms:
        return f'{_STYLE}<section class="apex-algorithms"><p>No algorithms found.</p></section>'
    rows = []
    for algorithm in algorithms:
        rows.append(
            "<tr><td><details>"
            f"<summary>{_text(algorithm.title or algorithm.id)}</summary>"
            f"{_details(algorithm)}</details>"
            f'<div class="apex-id">{_text(algorithm.id)}</div></td>'
            f"<td>{_text(algorithm.provider)}</td>"
            f"<td>{_text(', '.join(algorithm.platforms))}</td>"
            f"<td>{_text(', '.join(algorithm.keywords))}</td></tr>"
        )
    return (
        f'{_STYLE}<section class="apex-algorithms" aria-label="Algorithm catalogue">'
        f'<div class="apex-scroll"><table><caption>{heading}</caption>'
        '<thead><tr><th scope="col">Algorithm</th><th scope="col">Provider</th>'
        '<th scope="col">Platforms</th><th scope="col">Keywords</th></tr></thead>'
        f"<tbody>{''.join(rows)}</tbody></table></div></section>"
    )
