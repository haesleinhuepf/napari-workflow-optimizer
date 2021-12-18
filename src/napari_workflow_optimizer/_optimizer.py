from napari_time_slicer._workflow import Workflow
from scipy.optimize import minimize
import numpy as np

class Optimizer():
    def __init__(self, workflow: Workflow):
        self._workflow = workflow
        self._numeric_parameter_indices = self._find_numeric_parameters()
        self._fixed_parameters = np.zeros((len(self._numeric_parameter_indices)))
        print(len(self._numeric_parameter_indices), len(self._fixed_parameters))
        self._attempt = None
        self._quality = None
        self._running = False

    def _find_numeric_parameters(self):
        numeric_type_indices = []
        for name in self._workflow._tasks.keys():
            task = self._workflow.get_task(name)
            if callable(task[0]):
                for i, parameter in enumerate(task[1:]):
                    if isinstance(parameter, (int, float)):
                        numeric_type_indices.append([name, i + 1])
        return numeric_type_indices

    def get_numeric_parameters(self):
        result = []
        for parameter_index, [name, index] in enumerate(self._numeric_parameter_indices):
            if self._fixed_parameters[parameter_index] == 0:
                result.append(self._workflow.get_task(name)[index])
        return result

    def set_numeric_parameters(self, x):
        counter = 0
        for parameter_index, [name, index] in enumerate(self._numeric_parameter_indices):
            if self._fixed_parameters[parameter_index] == 0:
                task = list(self._workflow.get_task(name))
                task[index] = x[counter]
                self._workflow.set_task(name, tuple(task))
                counter += 1

    def get_all_numeric_parameters(self):
        result = []
        for name, index in self._numeric_parameter_indices:
            result.append(self._workflow.get_task(name)[index])
        return result

    def get_all_numeric_parameter_names(self):
        result = []
        import inspect
        for name, index in self._numeric_parameter_indices:
            task = self._workflow.get_task(name)
            func = task[0]
            sig = inspect.signature(func)
            parameter_names = list(sig.parameters.keys())
            result.append([name, parameter_names[index - 1]])

        return result

    def total_number_of_parameters(self):
        return len(self._numeric_parameter_indices)

    def fix_parameter(self, index):
        self._fixed_parameters[index] = 1

    def free_parameter(self, index):
        self._fixed_parameters[index] = 0

    def optimize(self, target_task, annotation, method='nelder-mead', maxiter=100, debug_output=False):
        self._counter = 0
        self._attempt = []
        self._quality = []
        self._settings = []
        self._running = True

        def fun(x):
            self._counter += 1
            # apply current parameter setting
            self.set_numeric_parameters(x)
            try:
                test = self._workflow.get(target_task)
            except:
                if len(self._quality) > 0:
                    quality = np.max(self._quality)
                else:
                    quality = np.finfo(float).max

            # as we are minimizing, we multiply fitness with -1
            quality = -self._fitness(test, annotation)

            if debug_output:
                print(self._counter, x, quality)

            self._attempt.append(len(self._attempt) + 1)
            self._quality.append(-quality)
            self._settings.append(x)

            return quality

        # starting point in parameter space
        x0 = self.get_numeric_parameters()

        # run the optimization
        options = {
            'xatol': 1e-3,
            'disp': debug_output,
            'maxiter': maxiter}
        res = minimize(fun, x0, method=method, options=options)

        # print and show result
        print(res)
        self.set_numeric_parameters(x0)

        self._running = False

        return res['x']

    def get_plot(self):
        return self._attempt, self._quality

    def is_running(self):
        return self._running

class SparseAnnotatedBinaryImageOptimizer(Optimizer):
    def __init__(self, workflow: Workflow):
        super().__init__(workflow)

    def _fitness(self, test, reference):
        """
        Determine how correct a given test segmentation is.
        As metric we use the Jaccard index.
        Assumtion: test is a binary image(0=False and 1=True) and
        reference is an image with 0=unknown, 1=False, 2=True.
        """
        # cle.imshow(test)
        # cle.imshow(reference)

        import pyclesperanto_prototype as cle
        binary_and = cle.binary_and

        negative_reference = reference == 1
        positive_reference = reference == 2
        negative_test = test == 0
        positive_test = test == 1

        # true positive: test = 1, ref = 2
        tp = binary_and(positive_reference, positive_test).sum()

        # true negative:
        tn = binary_and(negative_reference, negative_test).sum()

        # false positive
        fp = binary_and(negative_reference, positive_test).sum()

        # false negative
        fn = binary_and(positive_reference, negative_test).sum()

        #print(tp, tn, fp, fn)

        # return Jaccard Index
        return tp / (tp + fn + fp)


class JaccardLabelImageOptimizer(Optimizer):
    def __init__(self, workflow: Workflow):
        super().__init__(workflow)

    def _fitness(self, test, reference):
        # from https://github.com/BiAPoL/biapol-utilities/blob/main/biapol_utilities/label/_intersection_over_union.py
        from sklearn.metrics import confusion_matrix
        import numpy as np
        overlap = confusion_matrix(reference.ravel(), test.ravel())

        # Measure correctly labeled pixels
        n_pixels_pred = np.sum(overlap, axis=0, keepdims=True)
        n_pixels_true = np.sum(overlap, axis=1, keepdims=True)

        # Caluclate intersection over union
        iou = overlap / (n_pixels_pred + n_pixels_true - overlap)
        iou[np.isnan(iou)] = 0.0

        max_jacc = iou.max(axis=1)

        quality = max_jacc.mean()

        return quality


class MeanSquaredErrorImageOptimizer(Optimizer):
    def __init__(self, workflow: Workflow):
        super().__init__(workflow)

    def _fitness(self, test, reference):
        import pyclesperanto_prototype as cle
        return 1/cle.mean_squared_error(test, reference)
