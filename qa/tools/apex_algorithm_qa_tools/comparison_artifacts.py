"""
Generate visual comparison artifacts (PNG previews + interactive Leaflet maps)
between *actual* and *reference* benchmark output, for inclusion in GitHub
issues when a scenario fails on the ``compare`` phase.

Supported file formats
----------------------
* **2D raster**: ``.tif`` / ``.tiff`` / ``.nc`` — produces a 3-panel PNG
  (reference / actual / abs-diff) plus, when the data is georeferenced,
  a self-contained Folium HTML. The reference is always shown:
  in the PNG it is the leftmost panel and in the interactive map it is
  pinned as a non-toggleable base layer, so toggling Actual / Diff always
  overlays them on top of the reference.
  Multi-band / multi-time data is exploded into one artifact per
  ``(variable, band, time)`` slice.
* **1D tabular**: ``.csv`` / ``.json`` / ``.parquet`` — produces a PNG with
  one matplotlib subplot per numeric column (reference vs. actual + residual).

Heavy/optional dependencies (``matplotlib``, ``folium``, ``rioxarray``,
``pyarrow``) are imported lazily so that this module can be imported even
when one of them is missing; in that case the corresponding format is simply
skipped with a warning.

Usage
-----
The single public entry point is :func:`build_comparison_artifacts`::

    artifacts = build_comparison_artifacts(
        actual_dir=Path("./actual"),
        reference_dir=Path("./reference"),
        out_dir=Path("./comparison"),
    )
    for art in artifacts:
        print(art.title, art.png_path, art.html_path, art.summary)
"""

from __future__ import annotations

import dataclasses
import json
import logging
from pathlib import Path
from typing import Iterable, List, Optional

logger = logging.getLogger(__name__)


# File extension dispatch
_RASTER_EXTS = {".tif", ".tiff", ".nc"}
_TABULAR_EXTS = {".csv", ".json", ".parquet"}


@dataclasses.dataclass(frozen=True)
class ComparisonArtifact:
    """A single visual comparison artifact for one slice of data."""

    title: str
    """Human-readable title, e.g. ``"openEO.tif — band B04"``."""

    png_path: Optional[Path] = None
    """Path to a static PNG showing reference / actual / diff."""

    html_path: Optional[Path] = None
    """Path to a self-contained interactive Leaflet HTML (only for georeferenced rasters)."""

    summary: str = ""
    """Short text summary, e.g. ``"max abs diff: 0.012, 3 px > tol"``."""

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "png_path": str(self.png_path) if self.png_path else None,
            "html_path": str(self.html_path) if self.html_path else None,
            "summary": self.summary,
        }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def build_comparison_artifacts(
    actual_dir: Path,
    reference_dir: Path,
    out_dir: Path,
) -> List[ComparisonArtifact]:
    """
    Walk ``reference_dir`` and produce comparison artifacts for every file
    that has a counterpart in ``actual_dir`` and a supported extension.

    Returns a (possibly empty) list of :class:`ComparisonArtifact`.
    Errors per file are caught and logged; a failing file does not abort the
    whole comparison.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    artifacts: List[ComparisonArtifact] = []

    for ref_path in sorted(reference_dir.rglob("*")):
        if not ref_path.is_file():
            continue
        rel = ref_path.relative_to(reference_dir)
        actual_path = actual_dir / rel
        if not actual_path.is_file():
            logger.info(f"No actual counterpart for reference {rel}, skipping")
            continue

        ext = ref_path.suffix.lower()
        try:
            if ext in _RASTER_EXTS:
                artifacts.extend(
                    _compare_raster(
                        actual_path=actual_path,
                        reference_path=ref_path,
                        out_dir=out_dir,
                        base_name=str(rel).replace("/", "__"),
                    )
                )
            elif ext in _TABULAR_EXTS:
                art = _compare_tabular(
                    actual_path=actual_path,
                    reference_path=ref_path,
                    out_dir=out_dir,
                    base_name=str(rel).replace("/", "__"),
                )
                if art is not None:
                    artifacts.append(art)
            else:
                logger.debug(f"Skipping unsupported file type: {rel}")
        except Exception as e:
            logger.warning(
                f"Failed to build comparison artifact for {rel}: {e!r}", exc_info=True
            )

    return artifacts


# ---------------------------------------------------------------------------
# Raster (GeoTIFF / NetCDF) comparison
# ---------------------------------------------------------------------------

def _compare_raster(
    *,
    actual_path: Path,
    reference_path: Path,
    out_dir: Path,
    base_name: str,
) -> List[ComparisonArtifact]:
    """Open as xarray and produce one artifact per (var, band, time) slice."""
    try:
        import xarray as xr  # noqa: F401
    except ImportError:
        logger.warning("xarray not available; cannot compare raster files")
        return []

    actual_ds = _open_as_dataset(actual_path)
    ref_ds = _open_as_dataset(reference_path)

    artifacts: List[ComparisonArtifact] = []

    var_names = sorted(set(actual_ds.data_vars) & set(ref_ds.data_vars)) or [None]
    for var_name in var_names:
        actual_da = actual_ds[var_name] if var_name else _first_var(actual_ds)
        ref_da = ref_ds[var_name] if var_name else _first_var(ref_ds)

        # Iterate over every non-spatial dim combination.
        for slice_label, actual_slice, ref_slice in _iter_2d_slices(actual_da, ref_da):
            title_parts = [base_name]
            if var_name and var_name != base_name:
                title_parts.append(var_name)
            if slice_label:
                title_parts.append(slice_label)
            title = " — ".join(title_parts)

            slice_id = "_".join(
                _safe(p) for p in [base_name, var_name or "", slice_label] if p
            ) or _safe(base_name)
            png_path = out_dir / f"{slice_id}.png"
            html_path = out_dir / f"{slice_id}.html"

            summary = _render_raster_png(
                actual=actual_slice,
                reference=ref_slice,
                out_path=png_path,
                title=title,
            )

            html_written = _render_raster_folium(
                actual=actual_slice,
                reference=ref_slice,
                out_path=html_path,
                title=title,
            )

            artifacts.append(
                ComparisonArtifact(
                    title=title,
                    png_path=png_path if png_path.exists() else None,
                    html_path=html_path if html_written else None,
                    summary=summary,
                )
            )

    return artifacts


def _open_as_dataset(path: Path):
    """Open .tif / .nc as an :class:`xarray.Dataset`."""
    import xarray as xr

    ext = path.suffix.lower()
    if ext in {".tif", ".tiff"}:
        import rioxarray  # noqa: F401  -- registers the .rio accessor

        da = xr.open_dataarray(path, engine="rasterio")
        # Promote to dataset under the file stem so naming is consistent.
        return da.to_dataset(name=path.stem)
    elif ext == ".nc":
        return xr.open_dataset(path)
    else:
        raise ValueError(f"Unsupported raster extension: {ext}")


def _first_var(ds):
    name = next(iter(ds.data_vars))
    return ds[name]


def _iter_2d_slices(actual_da, ref_da):
    """Yield ``(label, actual_2d, reference_2d)`` for every non-spatial slice.

    Spatial dims are detected as the last two dims, or named (x, y) /
    (lon, lat) / (longitude, latitude) when present.
    """
    spatial_dims = _detect_spatial_dims(actual_da)
    extra_dims = [d for d in actual_da.dims if d not in spatial_dims]

    if not extra_dims:
        yield "", actual_da, ref_da
        return

    # Build cartesian product of coord values.
    import itertools

    coord_lists = []
    for d in extra_dims:
        coords = (
            list(actual_da.coords[d].values)
            if d in actual_da.coords
            else list(range(actual_da.sizes[d]))
        )
        coord_lists.append([(d, c) for c in coords])

    for combo in itertools.product(*coord_lists):
        sel = {d: c for d, c in combo}
        label = ", ".join(f"{d}={_fmt_coord(c)}" for d, c in combo)
        try:
            a = actual_da.sel(sel) if all(d in actual_da.coords for d, _ in combo) else actual_da.isel(
                {d: list(actual_da.coords[d].values).index(c) if d in actual_da.coords else c for d, c in combo}
            )
            r = ref_da.sel(sel) if all(d in ref_da.coords for d, _ in combo) else ref_da.isel(
                {d: list(ref_da.coords[d].values).index(c) if d in ref_da.coords else c for d, c in combo}
            )
        except Exception as e:
            logger.debug(f"Skipping slice {label}: {e!r}")
            continue
        yield label, a, r


def _detect_spatial_dims(da) -> tuple:
    candidates = [
        ("y", "x"),
        ("lat", "lon"),
        ("latitude", "longitude"),
    ]
    dims = set(da.dims)
    for c in candidates:
        if set(c).issubset(dims):
            return c
    # Fallback: last two dims.
    return tuple(da.dims[-2:])


def _fmt_coord(c) -> str:
    import numpy as np

    if isinstance(c, (np.datetime64,)):
        return str(c)[:10]
    if isinstance(c, float):
        return f"{c:.4g}"
    return str(c)


def _safe(s: str) -> str:
    import re

    return re.sub(r"[^a-zA-Z0-9._-]+", "_", str(s)).strip("_")


def _render_raster_png(*, actual, reference, out_path: Path, title: str) -> str:
    """Render the 3-panel comparison PNG. Returns a one-line summary string."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        logger.warning("matplotlib not available; cannot render PNG")
        return ""

    a = np.asarray(actual.values, dtype="float64")
    r = np.asarray(reference.values, dtype="float64")
    diff = a - r
    abs_diff = np.abs(diff)
    finite = np.isfinite(abs_diff)
    max_abs = float(np.nanmax(abs_diff)) if finite.any() else float("nan")
    mean_abs = float(np.nanmean(abs_diff)) if finite.any() else float("nan")

    vmin = float(np.nanmin(np.stack([a, r])))
    vmax = float(np.nanmax(np.stack([a, r])))

    fig, axes = plt.subplots(1, 3, figsize=(15, 5), constrained_layout=True)
    im0 = axes[0].imshow(r, vmin=vmin, vmax=vmax, cmap="viridis")
    axes[0].set_title("Reference")
    plt.colorbar(im0, ax=axes[0], shrink=0.7)

    im1 = axes[1].imshow(a, vmin=vmin, vmax=vmax, cmap="viridis")
    axes[1].set_title("Actual")
    plt.colorbar(im1, ax=axes[1], shrink=0.7)

    diff_max = max(max_abs, 1e-12)
    im2 = axes[2].imshow(diff, vmin=-diff_max, vmax=diff_max, cmap="RdBu_r")
    axes[2].set_title("Actual − Reference")
    plt.colorbar(im2, ax=axes[2], shrink=0.7)

    fig.suptitle(title, fontsize=11)
    for ax in axes:
        ax.set_xticks([])
        ax.set_yticks([])

    fig.savefig(out_path, dpi=110)
    plt.close(fig)

    return f"max |Δ| = {max_abs:.4g}, mean |Δ| = {mean_abs:.4g}"


def _render_raster_folium(*, actual, reference, out_path: Path, title: str) -> bool:
    """Render an interactive Leaflet HTML. Returns True on success."""
    try:
        import folium
        import numpy as np
        import rioxarray  # noqa: F401
    except ImportError:
        logger.info("folium / rioxarray not available; skipping interactive map")
        return False

    # Need a CRS to make a map.
    try:
        crs = actual.rio.crs
    except Exception:
        crs = None
    if crs is None:
        logger.info(f"No CRS on {title}; skipping interactive map")
        return False

    try:
        actual_4326 = actual.rio.reproject("EPSG:4326")
        ref_4326 = reference.rio.reproject("EPSG:4326")
    except Exception as e:
        logger.warning(f"Reprojection to EPSG:4326 failed for {title}: {e!r}")
        return False

    a_arr = np.asarray(actual_4326.values, dtype="float64")
    r_arr = np.asarray(ref_4326.values, dtype="float64")
    diff = a_arr - r_arr

    # Bounds: try .rio.bounds() (left, bottom, right, top)
    try:
        left, bottom, right, top = actual_4326.rio.bounds()
    except Exception as e:
        logger.warning(f"No bounds for {title}: {e!r}")
        return False

    bounds = [[bottom, left], [top, right]]
    center = [(bottom + top) / 2, (left + right) / 2]

    fmap = folium.Map(location=center, zoom_start=10, tiles="OpenStreetMap")

    # Reference layer: always visible, NOT in the layer control — toggling other
    # overlays should never make the map empty.
    folium.raster_layers.ImageOverlay(
        image=_normalize_to_rgba(r_arr, cmap="viridis"),
        bounds=bounds,
        opacity=1.0,
        name="Reference (always shown)",
        control=False,
    ).add_to(fmap)

    folium.raster_layers.ImageOverlay(
        image=_normalize_to_rgba(a_arr, cmap="viridis"),
        bounds=bounds,
        opacity=0.8,
        name="Actual",
        show=False,
    ).add_to(fmap)

    folium.raster_layers.ImageOverlay(
        image=_normalize_to_rgba(diff, cmap="RdBu_r", symmetric=True),
        bounds=bounds,
        opacity=0.8,
        name="Actual − Reference",
        show=False,
    ).add_to(fmap)

    folium.LayerControl(collapsed=False).add_to(fmap)
    fmap.fit_bounds(bounds)

    title_html = (
        f'<div style="position:fixed;top:8px;left:50px;z-index:1000;'
        f'background:rgba(255,255,255,0.85);padding:4px 8px;'
        f'font-family:sans-serif;font-size:13px;border-radius:4px;">'
        f"<b>{title}</b></div>"
    )
    fmap.get_root().html.add_child(folium.Element(title_html))

    fmap.save(str(out_path))
    return True


def _normalize_to_rgba(arr, *, cmap: str = "viridis", symmetric: bool = False):
    """Map a 2D float array to an HxWx4 uint8 RGBA array using a matplotlib cmap."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.cm as mcm
    import numpy as np

    a = np.asarray(arr, dtype="float64")
    if symmetric:
        m = float(np.nanmax(np.abs(a))) or 1.0
        vmin, vmax = -m, m
    else:
        vmin = float(np.nanmin(a))
        vmax = float(np.nanmax(a))
        if vmax == vmin:
            vmax = vmin + 1.0
    norm = (a - vmin) / (vmax - vmin)
    norm = np.clip(norm, 0, 1)
    rgba = (mcm.get_cmap(cmap)(norm) * 255).astype("uint8")
    # Make NaN transparent.
    rgba[..., 3] = np.where(np.isfinite(a), 255, 0)
    return rgba


# ---------------------------------------------------------------------------
# Tabular (CSV / JSON / Parquet) comparison
# ---------------------------------------------------------------------------

def _compare_tabular(
    *,
    actual_path: Path,
    reference_path: Path,
    out_dir: Path,
    base_name: str,
) -> Optional[ComparisonArtifact]:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
        import pandas as pd
    except ImportError:
        logger.warning("pandas/matplotlib not available; cannot compare tabular data")
        return None

    try:
        actual_df = _read_tabular(actual_path)
        ref_df = _read_tabular(reference_path)
    except Exception as e:
        logger.warning(f"Failed reading tabular {actual_path.name}: {e!r}")
        return None

    if actual_df is None or ref_df is None:
        return None

    common_cols = [
        c for c in ref_df.columns
        if c in actual_df.columns
        and pd.api.types.is_numeric_dtype(ref_df[c])
        and pd.api.types.is_numeric_dtype(actual_df[c])
    ]
    if not common_cols:
        logger.info(f"No common numeric columns in {base_name}, skipping")
        return None

    n = len(common_cols)
    fig, axes = plt.subplots(n, 2, figsize=(12, 2.8 * n), squeeze=False)
    max_abs = 0.0
    for i, col in enumerate(common_cols):
        r = ref_df[col].to_numpy(dtype="float64")
        a = actual_df[col].to_numpy(dtype="float64")
        n_pts = min(len(r), len(a))
        r, a = r[:n_pts], a[:n_pts]
        x = np.arange(n_pts)
        axes[i, 0].plot(x, r, label="reference", linewidth=1.2)
        axes[i, 0].plot(x, a, label="actual", linewidth=1.2, alpha=0.8)
        axes[i, 0].set_title(f"{col}")
        axes[i, 0].legend(fontsize=8)

        diff = a - r
        axes[i, 1].plot(x, diff, color="firebrick", linewidth=1.0)
        axes[i, 1].axhline(0, color="black", linewidth=0.5)
        axes[i, 1].set_title(f"{col}: actual − reference")
        finite = np.isfinite(diff)
        if finite.any():
            max_abs = max(max_abs, float(np.nanmax(np.abs(diff))))

    fig.suptitle(base_name, fontsize=11)
    fig.tight_layout()
    png_path = out_dir / f"{_safe(base_name)}.png"
    fig.savefig(png_path, dpi=110)
    plt.close(fig)

    return ComparisonArtifact(
        title=base_name,
        png_path=png_path,
        html_path=None,
        summary=f"{n} numeric column(s); max |Δ| = {max_abs:.4g}",
    )


def _read_tabular(path: Path):
    import pandas as pd

    ext = path.suffix.lower()
    if ext == ".csv":
        return pd.read_csv(path)
    if ext == ".parquet":
        return pd.read_parquet(path)
    if ext == ".json":
        try:
            return pd.read_json(path)
        except ValueError:
            # records-style or single object
            with path.open("r", encoding="utf8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return pd.DataFrame(data)
            if isinstance(data, dict):
                # try treating dict-of-lists as a frame
                try:
                    return pd.DataFrame(data)
                except Exception:
                    return None
            return None
    return None


# ---------------------------------------------------------------------------
# Markdown rendering helper
# ---------------------------------------------------------------------------

def render_artifacts_markdown(
    artifacts: Iterable[dict],
) -> str:
    """
    Render a list of artifact dicts (each with ``title``, ``preview_url``,
    ``interactive_url``, ``summary``) as a markdown section suitable for a
    GitHub issue body.
    """
    lines: List[str] = []
    for art in artifacts:
        title = art.get("title", "")
        summary = art.get("summary", "")
        preview = art.get("preview_url")
        interactive = art.get("interactive_url")

        header = f"#### {title}"
        if summary:
            header += f"  &nbsp;_{summary}_"
        lines.append(header)
        if preview:
            lines.append(f"![preview]({preview})")
        if interactive:
            lines.append(f"🔍 [Open interactive map]({interactive})")
        lines.append("")  # blank line between artifacts
    return "\n".join(lines).rstrip() + "\n"
