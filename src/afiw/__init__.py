"""Antarctic Fast Ice Watch: laptop-first research workflows."""
from .core.types import (RegionSpec, RunSpec, AcquisitionSpec, ProcessingSpec, SegmentationSpec, SnapSpec, WorkflowSpec, PairResult)
from .core.paths import AFIWPaths
from .workflows.primary import PrimaryWorkflow
__version__ = "0.1.0"
