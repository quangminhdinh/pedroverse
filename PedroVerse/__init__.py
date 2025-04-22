"""
Stylization module exposing core effects: pixelation, brush strokes, and Voronoi stylization.
"""




from .geometric_abstruction import (
    pixelate,
    apply_brush_strokes,
    apply_voronoi,
    apply_brushstyle,
    apply_slic

)

from .utils import (
    apply_uv_mask_from_arrays,
    edge_detection,
    apply_bilateral_filter
)
