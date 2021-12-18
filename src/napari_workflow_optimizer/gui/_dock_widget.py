"""
This module is an example of a barebones QWidget plugin for napari

It implements the ``napari_experimental_provide_dock_widget`` hook specification.
see: https://napari.org/docs/dev/plugins/hook_specifications.html

Replace code below according to your needs.
"""
from napari_plugin_engine import napari_hook_implementation
from qtpy.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QCheckBox, QLabel
from magicgui import magic_factory

from napari_workflow_optimizer._optimizer import JaccardLabelImageOptimizer
from napari_time_slicer import WorkflowManager
from napari.layers import Labels
from magicgui.widgets import create_widget
from napari_tools_menu import register_dock_widget
import warnings

@register_dock_widget(menu="Utilities > Workflow optimizer (Labels)")
class WorkflowOptimizer(QWidget):
    def __init__(self, napari_viewer, optimizer_class=JaccardLabelImageOptimizer):
        super().__init__()
        self.viewer = napari_viewer

        self._manager = WorkflowManager.install(napari_viewer)
        self._optimizer = optimizer_class(self._manager.workflow)

        self.labels_select = create_widget(annotation=Labels, label="Target")
        self.reference_select = create_widget(annotation=Labels, label="Reference")
        self.maxiter_select = create_widget(widget_type="SpinBox",
                                        name='iterations',
                                        value=10,
                                        options=dict(min=1, step=1))

        self.setLayout(QVBoxLayout())
        self.layout().addWidget(QLabel("Select parameters to optimize"))
        self._parameter_checkboxes = []
        for layer_name, parameter_name in self._optimizer.get_all_numeric_parameter_names():
            name = layer_name.replace("Result of", "").replace("result", "").strip() + "." + parameter_name
            checkbox = QCheckBox(name)
            checkbox.setChecked(True)
            self._parameter_checkboxes.append(checkbox)
            self.layout().addWidget(checkbox)

        self._push_button = QPushButton("Start optimization")
        self._push_button.clicked.connect(self._on_run_click)

        self._undo_button = QPushButton("Undo")
        self._undo_button.clicked.connect(self._on_undo_click)
        self._undo_button.setVisible(False)

        self.layout().addWidget(vertical_widget(QLabel("Target"), self.labels_select.native))
        self.layout().addWidget(vertical_widget(QLabel("Reference"), self.reference_select.native))
        self.layout().addWidget(vertical_widget(QLabel("Number of iterations"), self.maxiter_select.native))
        self.layout().addWidget(vertical_widget(self._push_button, self._undo_button))
        self.layout().setSpacing(10)
        self._result_plot = None

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.reset_choices()

    def reset_choices(self, event=None):
        self.labels_select.reset_choices(event)
        self.reference_select.reset_choices(event)

    def _on_undo_click(self):
        self._optimizer.set_numeric_parameters(self._original_parameters)
        self._undo_button.setVisible(False)
        if self._result_plot is not None: # remove old plot if it existed already
            self.layout().removeWidget(self._result_plot)
        self.update_viewer()

    def _on_run_click(self):
        if self._optimizer.is_running():
            self._push_button.setText("Cancelling...")
            self._optimizer.cancel()
            return
        # Store original parameters in case we want to go back to them later.
        self._original_parameters = self._optimizer.get_numeric_parameters()
        self._undo_button.setVisible(False)

        # Configure which parameters are constants (fix) and which should be optimized (free).
        for index, checkbox in enumerate(self._parameter_checkboxes):
            if not checkbox.isChecked():
                self._optimizer.fix_parameter(index)
            else:
                self._optimizer.free_parameter(index)

        # Before we can optimize the workflow, we need to pass input images.
        # Those are all layers that are not computed. Hence, we pass all layer-data
        # to the workflow which doesn't exist yet.
        for layer in self.viewer.layers:
            workflow = self._manager.workflow
            try:
                workflow.get_task(layer.name)
            except KeyError:
                print("Setting data", layer.name)
                workflow.set(layer.name, layer.data)

        from napari._qt.qthreading import thread_worker
        import time

        self._maxiter = self.maxiter_select.value

        # Optimization runs in a background thread
        @thread_worker
        def optimize_runner():
            yield self._optimizer.optimize(
                self.labels_select.value.name,
                self.reference_select.value.data,
                maxiter=self._maxiter,
                debug_output=True)

        # Update progress/status in a separate thread
        from napari.utils import progress
        self._progress_reporter = progress(total=self.maxiter_select.value)

        @thread_worker
        def status_runner():
            while True:
                time.sleep(0.2)
                is_running = self._optimizer.is_running()
                yield is_running
                if is_running and not self._optimizer.is_cancelling():
                    self._push_button.setText("Cancel (" + str(self._iteration_count) + "/" + str(self._maxiter) + ")")
                else:
                    return

        # In case progress is updated, update the GUI from the main thread:
        self._iteration_count = 0
        def yield_progress(is_running):
            #print("Update status")
            if is_running:
                self._progress_reporter.set_description("Optimization")
                _, quality = self._optimizer.get_plot()
                if self._iteration_count != len(quality):
                    self._progress_reporter.update(len(quality) - self._iteration_count)
                    self._iteration_count = len(quality)
                    self._plot_quality()
            #print("Status updated")

        # When the optimization is done, update the GUI from the main thread:
        def yield_result(best_result):
            self._optimizer.set_numeric_parameters(best_result)
            self._plot_quality()
            self._push_button.setText("Start optimization again")
            self._progress_reporter.close()

            self._undo_button.setVisible(True)

            # update result
            self.update_viewer()

        # Start optimization and progress/status updates
        optimize_worker = optimize_runner()
        optimize_worker.yielded.connect(yield_result)
        optimize_worker.start()
        status_worker = status_runner()
        status_worker.yielded.connect(yield_progress)
        status_worker.start()

    def _plot_quality(self):
        # show result as plot
        iteration, quality = self._optimizer.get_plot()
        from ._plotter import PlotterWidget
        plotter_widget = PlotterWidget(iteration, quality, "Iteration", "Quality")
        if self._result_plot is not None: # remove old plot if it existed already
            self.layout().removeWidget(self._result_plot)
        self._result_plot = plotter_widget
        self.layout().addWidget(self._result_plot)

    def update_viewer(self):
        WIDGET_KEY = "magic_gui_widget"

        def find_widget(parent, name):
            if hasattr(parent, name):
                return getattr(parent, name)

            from napari_pyclesperanto_assistant._gui._category_widget import category_args_numeric
            for n in category_args_numeric:
                if hasattr(parent, n):
                    widget = getattr(parent, n)
                    if widget.label == name:
                        return widget

        for [layer_name, parameter_name], value in zip(
                self._optimizer.get_all_numeric_parameter_names(),
                self._optimizer.get_all_numeric_parameters()):
            layer = self.viewer.layers[layer_name]

            if WIDGET_KEY in layer.metadata:
                print("Updating", layer_name, parameter_name, value)
                widget = layer.metadata[WIDGET_KEY]
                parameter_widget = find_widget(widget, parameter_name)
                if parameter_widget is not None:
                    parameter_widget.native.setValue(value)
                else:
                    warnings.warn("Can't update widget for " + layer_name + " " + parameter_name)
            else:
                warnings.warn("Can't find widget for " + layer_name + " " + parameter_name)

def vertical_widget(left, right):
    widget = QWidget()
    widget.setLayout(QHBoxLayout())
    widget.layout().addWidget(left)
    widget.layout().addWidget(right)
    widget.layout().setSpacing(1)
    widget.layout().setContentsMargins(0,0,0,0)

    return widget


@magic_factory
def example_magic_widget(img_layer: "napari.layers.Image"):
    print(f"you have selected {img_layer}")


@napari_hook_implementation
def napari_experimental_provide_dock_widget():
    # you can return either a single widget, or a sequence of widgets
    return [WorkflowOptimizer, example_magic_widget]
