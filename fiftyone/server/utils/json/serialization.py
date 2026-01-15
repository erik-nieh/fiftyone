"""JSON serialization

| Copyright 2017-2026, Voxel51, Inc.
| `voxel51.com <https://voxel51.com/>`_
|
"""

from typing import Any

import fiftyone.core.labels as fol
import fiftyone.core.sample as fos
import fiftyone.core.fields as fof
from fiftyone.core.singletons import fo


def deserialize(value: Any) -> Any:
    """Deserializes a value into an a known type.

    Args:
        value: The value to deserialize

    Returns:
        The deserialized value if able to deserialize, otherwise the input
        value.
    """
    import logging
    logger = logging.getLogger(__name__)
    if isinstance(value, dict):
        logger.info("value: %s", value)
        if cls_name := value.get("_cls"):
            logger.info("cls_name: %s", cls_name)
            cls = next(
                (
                    cls
                    for cls in (
                        fol.Classification,
                        fol.Classifications,
                        fol.Detection,
                        fol.Detections,
                        fol.Polyline,
                        fol.Polylines,
                        fof.DateTimeField,
                    )
                    if cls.__name__ == cls_name
                ),
                None,
            )

            if cls is None:
                logger.info("cls is None")
                raise ValueError(
                    f"No deserializer registered for class '{cls_name}'"
                )
            logger.info("cls 2: %s", cls)
            return cls.from_dict(value)

    return value


def serialize(value: Any) -> Any:
    """Serializes an value

    Args:
        value: The value to serialize

    Returns:
        The serialized value if able to serialize, otherwise the input value.
    """

    cls = type(value)
    if cls == fos.Sample:
        return value.to_dict(include_private=True)

    if hasattr(value, "to_dict"):
        return value.to_dict()

    return value
