
__version__ = "0.1.4"


from ._optimizer import JaccardLabelImageOptimizer, \
    SparseAnnotatedBinaryImageOptimizer, \
    MeanSquaredErrorImageOptimizer, \
    Optimizer, \
    Workflow

from napari_workflow_optimizer.gui._dock_widget import napari_experimental_provide_dock_widget

