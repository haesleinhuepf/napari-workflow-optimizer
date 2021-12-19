from napari_time_slicer._workflow import Workflow
from scipy.optimize import minimize
import numpy as np

class Optimizer():
    def __init__(self, workflow: Workflow):
        self._workflow = workflow
        self._numeric_parameter_indices = self._find_numeric_parameters()
        self._fixed_parameters = np.zeros((len(self._numeric_parameter_indices)))
        self._iteration = None
        self._quality = None
        self._running = False
        self._canceling = False

    def _find_numeric_parameters(self):
        """
        Analyse the workflow, determine the numeric parameters and store the names of the given layers
        and corresponing parameter indices.
        """
        numeric_type_indices = []
        for name in self._workflow._tasks.keys():
            task = self._workflow.get_task(name)
            if callable(task[0]):
                for i, parameter in enumerate(task[1:]):
                    if isinstance(parameter, (int, float)):
                        numeric_type_indices.append([name, i + 1])
        return numeric_type_indices

    def get_numeric_parameters(self):
        """
        Returns all non-constant numeric parameters of the workflow.
        """
        result = []
        for parameter_index, [name, index] in enumerate(self._numeric_parameter_indices):
            if self._fixed_parameters[parameter_index] == 0:
                result.append(self._workflow.get_task(name)[index])
        return result

    def set_numeric_parameters(self, x):
        """
        Overwrites all non-constant numeric parameters of the workflow with a given list of numbers x.
        """
        counter = 0
        for parameter_index, [name, index] in enumerate(self._numeric_parameter_indices):
            if self._fixed_parameters[parameter_index] == 0:
                task = list(self._workflow.get_task(name))
                task[index] = x[counter]
                self._workflow.set_task(name, tuple(task))
                counter += 1

    def set_all_numeric_parameters(self, x):
        """
        Overwrites all numeric parameters of the workflow with a given list of numbers x.
        """
        for parameter_index, [name, index] in enumerate(self._numeric_parameter_indices):
            task = list(self._workflow.get_task(name))
            task[index] = x[parameter_index]
            self._workflow.set_task(name, tuple(task))

    def get_all_numeric_parameters(self):
        """
        Returns
        -------
        All numeric parameters in the workflow, including the constants.
        """
        result = []
        for name, index in self._numeric_parameter_indices:
            result.append(self._workflow.get_task(name)[index])
        return result

    def get_all_numeric_parameter_names(self):
        """
        Returns
        -------
        All names of numeric parameters in the workflow, including the constants.
        A name is a tuple consisting of the layer name and the parameter name.
        The layer name is typically related to the name of the function that generated the layer.
        """
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
        """
        Returns the number of numeric parameters in the workflow.
        """
        return len(self._numeric_parameter_indices)

    def fix_parameter(self, index):
        """
        The parameter with the given index becomes a constant in the optimization.
        """
        self._fixed_parameters[index] = 1

    def free_parameter(self, index):
        """
        The parameter with the given index becomes a variable in the optimization.
        """
        self._fixed_parameters[index] = 0

    def optimize(self, target_task, annotation, maxiter = 100, debug_output = False):
        """
        Optimizes the given workflow.

        Parameters
        ----------
        target_task: str
            The layer/task name which should be optimized
        annotation: ndarry
            Reference image
        maxiter: int
            Number of iterations
        debug_output: bool
            If set to true, every attempt will be prompted to stdout

        Returns
        -------
        List of numbers corresponding to the not-constant numeric parameters of a given workflow.
        """
        method = 'nelder-mead'
        self._counter = 0
        self._iteration = []
        self._quality = []
        self._settings = []
        self._running = True
        self._canceling = False

        from functools import lru_cache

        def fun(x):
            """
            Helper function to make num_fun lru-cachable.
            """
            return num_fun(*(x.tolist()))

        @lru_cache(maxsize=10)
        def num_fun(*x):
            """
            Determine quality of a given parameter set.

            Parameters
            ----------
            x : list of numbers
                numeric parameters of the workflow to be tested

            Returns
            -------
            quality, metric depends on implementation
            """
            self._counter += 1

            if len(self._quality) > 0 and self._canceling:
                return np.max(self._quality)

            # apply current parameter setting
            self.set_numeric_parameters(x)
            try:
                test = self._workflow.get(target_task)
            except:
                if len(self._quality) > 0:
                    quality = np.max(self._quality)
                else:
                    quality = np.finfo(float).max
                return quality

            # as we are minimizing, we multiply fitness with -1
            quality = -self._fitness(test, annotation)

            if debug_output:
                print(self._counter, x, quality)

            return quality

        def progress_callback(x):
            """
            This callback is executed when the optimizer finished one iteration.
            We then take the preliminary result and store it together with the
            corresponding quality.
            """
            if not self._canceling:
                quality = fun(x)
                self._iteration.append(len(self._iteration) + 1)
                self._quality.append(-quality)
                self._settings.append(x)

        # starting point in parameter space
        x0 = self.get_numeric_parameters()

        # run the optimization
        options = {
            'xatol': 1e-3,
            'disp': debug_output,
            'maxiter': maxiter}
        res = minimize(fun, x0, method=method, callback=progress_callback, options=options)

        # print and show result
        if debug_output:
            print(res)
        self.set_numeric_parameters(x0)

        self._running = False
        self._canceling = False

        return res['x']

    def get_plot(self):
        """
        Returns list of executed iterations numbers (a range) and corresponding measured quality values.
        """
        return self._iteration, self._quality

    def is_running(self):
        """
        Returns if the optimizer is currently running
        """
        return self._running

    def cancel(self):
        """
        In case the optimizer is running, we can interrupt it by calling this function.
        """
        self._canceling = True

    def is_cancelling(self):
        """
        Returns if the optimizier is currently cancelling.
        """
        return self._canceling

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

        # Calculate intersection over union
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
