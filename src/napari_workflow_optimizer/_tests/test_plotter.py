def test_plotter(make_napari_viewer):
    viewer = make_napari_viewer()

    from napari_workflow_optimizer.gui._plotter import PlotterWidget
    optimizer_gui = PlotterWidget([0,1],[0,1], "x", "y")

    num_dw = len(viewer.window._dock_widgets)
    viewer.window.add_dock_widget(optimizer_gui)
    assert len(viewer.window._dock_widgets) == num_dw + 1


