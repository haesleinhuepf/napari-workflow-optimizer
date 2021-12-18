from qtpy.QtWidgets import QWidget, QVBoxLayout
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

# from https://github.com/BiAPoL/napari-clusters-plotter/blob/main/napari_clusters_plotter/_plotter.py
class MplCanvas(FigureCanvas):

    def __init__(self, parent=None):
        self.fig = Figure()

        # changing color of axes background to napari main window color
        self.fig.patch.set_facecolor('#262930')
        self.axes = self.fig.add_subplot(111)

        # changing color of plot background to napari main window color
        self.axes.set_facecolor('#262930')

        # changing colors of all axes
        self.axes.spines['bottom'].set_color('white')
        self.axes.spines['top'].set_color('white')
        self.axes.spines['right'].set_color('white')
        self.axes.spines['left'].set_color('white')
        self.axes.xaxis.label.set_color('white')
        self.axes.yaxis.label.set_color('white')

        # changing colors of axes labels
        self.axes.tick_params(axis='x', colors='white')
        self.axes.tick_params(axis='y', colors='white')

        super(MplCanvas, self).__init__(self.fig)

        self.reset()

    def reset(self):
        self.axes.clear()


class PlotterWidget(QWidget):
    def __init__(self, x, y, xlabel, ylabel):
        super().__init__()

        # a figure instance to plot on
        self.figure = Figure()

        self.graphics_widget = MplCanvas(self.figure)

        self.setLayout(QVBoxLayout())
        self.layout().addWidget(self.graphics_widget)

        self.graphics_widget.axes.plot(x, y)
        self.graphics_widget.axes.set_xlabel(xlabel)
        self.graphics_widget.axes.xaxis.set_label_coords(0.5, 0.1)
        self.graphics_widget.axes.set_ylabel(ylabel)
        self.graphics_widget.axes.yaxis.set_label_coords(0.1, 0.5)
        self.graphics_widget.draw()

        #self.setMinimumWidth(300)
        #self.setMinimumHeight(150)
