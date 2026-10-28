"""Transform layer — column-type inference and the `ColumnTransformer` builder.

`TabularPreprocessor` is re-exported from `ml.model_comparison.compare` rather
than moved: it is the sentinel-fill + one-hot transformer harvested from a
deployed credit-scoring pipeline, still the right tool when a tree model wants
missingness encoded as a splittable value, and existing code imports it from its
original home. This layer extends it rather than replacing it.
"""

from __future__ import annotations

from ml.model_comparison.compare import TabularPreprocessor
from ml.transform.columns import (
    DEFAULT_HIGH_CARD_THRESHOLD,
    ColumnPlan,
    infer_column_types,
)
from ml.transform.encoders import (
    DatetimeFeatures,
    TargetEncoder,
    build_transformer,
)

__all__ = [
    "DEFAULT_HIGH_CARD_THRESHOLD",
    "ColumnPlan",
    "DatetimeFeatures",
    "TabularPreprocessor",
    "TargetEncoder",
    "build_transformer",
    "infer_column_types",
]
