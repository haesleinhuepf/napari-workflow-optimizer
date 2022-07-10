from skimage.io import imread
from napari_workflow_optimizer import SparseAnnotatedBinaryImageOptimizer, \
    MeanSquaredErrorImageOptimizer, \
    JaccardLabelImageOptimizer, \
    Workflow
import napari_segment_blobs_and_things_with_membranes as nsbatwm
import pyclesperanto_prototype as cle


def test_binary_image_optimizer():
    w = Workflow()
    # define background subtraction
    w.set("deblurred", cle.gaussian_blur, "input", sigma_x=5, sigma_y=5)
    # define segmentation
    w.set("binarized", cle.threshold_otsu, "deblurred")

    w.set("input", imread("demo/blobs.tif"))

    ground_truth = imread("demo/blobs_annotated.tif")

    sabio = SparseAnnotatedBinaryImageOptimizer(w)
    best_param = sabio.optimize("binarized", ground_truth, maxiter=5)
    sabio.set_numeric_parameters(best_param)

    result = w.get("binarized")

    print(result.sum())
    assert abs(result.sum() - 32178 <= 10)  # accept 10 wrongly set pixels


def test_intensity_image_optimizer():
    w = Workflow()
    # define background subtraction
    w.set("blurred", cle.gaussian_blur, "input", sigma_x=7, sigma_y=3)

    input_image = imread("demo/blobs.tif")
    w.set("input", input_image)

    ground_truth = cle.gaussian_blur(input_image, sigma_x=3, sigma_y=5)

    mseio = MeanSquaredErrorImageOptimizer(w)
    mseio.get_numeric_parameters()

    mseio.fix_parameter(2)
    mseio.get_numeric_parameters()

    best_param = mseio.optimize("blurred", ground_truth, maxiter=2)
    mseio.set_numeric_parameters(best_param)

    result = w.get("blurred")

    mse = cle.mean_squared_error(result, input_image)
    assert abs(mse - 1162) < 1 # accept a small absolute error compared to MSE


def test_membrane_segmentation():
    w = Workflow()
    w.set("labeled", nsbatwm.thresholded_local_minima_seeded_watershed, "input", spot_sigma=2, outline_sigma=2)

    w.set("input", imread("demo/membranes_2d.tif"))  # image data source: scikit-image cells3d example, slice 28

    ground_truth = imread("demo/membranes_2d_sparse_labels.tif")

    jlio = JaccardLabelImageOptimizer(w)
    jlio.get_numeric_parameters()

    best_param = jlio.optimize("labeled", ground_truth, maxiter=5)
    jlio.set_numeric_parameters(best_param)

    result = w.get("labeled")

    print(result.max())
    assert abs(result.max() - 125) < 2  # accept an error of 2 in object count


def test_sparse_label_image_optimizer():
    w = Workflow()
    w.set("labeled", cle.voronoi_otsu_labeling, "input", spot_sigma=1, outline_sigma=5)

    w.set("input", imread("demo/blobs.tif"))

    ground_truth = imread("demo/blobs_sparse_labels.tif")

    jlio = JaccardLabelImageOptimizer(w)
    best_param = jlio.optimize("labeled", ground_truth, maxiter=10)
    jlio.set_numeric_parameters(best_param)

    result = w.get("labeled")

    assert abs(result.max() - 122) < 2  # accept an error of 2 in object count
