#define PY_SSIZE_T_CLEAN
#define NPY_NO_DEPRECATED_API NPY_1_7_API_VERSION
#include <Python.h>
#include <numpy/arrayobject.h>
#include "bridct.h"
#include <stdint.h>
#include <stdlib.h>

#ifdef Py_GIL_DISABLED
#error "This experimental extension requires a GIL-enabled CPython build."
#endif

typedef struct {
    PyObject_HEAD
    bridct_plan *kernel;
    float *spectrum;
    size_t elements;
    int height, width, initialized, busy;
} Plan;

static int plan_init(Plan *self, PyObject *args, PyObject *kwargs)
{
    static char *names[] = {"height", "width", NULL};
    int height, width;
    if (self->initialized) {
        PyErr_SetString(PyExc_RuntimeError, "A Plan cannot be reinitialized.");
        return -1;
    }
    if (self->busy) {
        PyErr_SetString(PyExc_RuntimeError, "This Plan is already initializing or executing.");
        return -1;
    }
    self->busy = 1;
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "ii:Plan", names, &height, &width))
        goto fail;
    if (!bridct_supported(height, width)) {
        PyErr_SetString(PyExc_ValueError, "Both dimensions must be powers of two from 8 through 1024.");
        goto fail;
    }
    bridct_plan *kernel = bridct_plan_create(height, width);
    size_t elements = (size_t)height * (size_t)width;
    float *spectrum = malloc(elements * sizeof(float));
    if (!kernel || !spectrum) {
        bridct_plan_destroy(kernel);
        free(spectrum);
        PyErr_NoMemory();
        goto fail;
    }
    self->kernel = kernel;
    self->spectrum = spectrum;
    self->elements = elements;
    self->height = height;
    self->width = width;
    self->initialized = 1;
    self->busy = 0;
    return 0;

fail:
    self->busy = 0;
    return -1;
}

static void plan_dealloc(Plan *self)
{
    bridct_plan_destroy(self->kernel);
    free(self->spectrum);
    Py_TYPE(self)->tp_free((PyObject *)self);
}

static PyObject *plan_close(Plan *self, PyObject *unused)
{
    (void)unused;
    if (self->busy) {
        PyErr_SetString(PyExc_RuntimeError, "This Plan is already initializing or executing, possibly in another thread.");
        return NULL;
    }
    bridct_plan_destroy(self->kernel);
    self->kernel = NULL;
    free(self->spectrum);
    self->spectrum = NULL;
    Py_RETURN_NONE;
}

static PyArrayObject *checked_array(PyObject *object, const Plan *self, int output)
{
    if (!PyArray_CheckExact(object)) {
        PyErr_SetString(PyExc_TypeError, "Expected an exact NumPy ndarray; no implicit conversion is performed.");
        return NULL;
    }
    PyArrayObject *array = (PyArrayObject *)object;
    if (PyArray_TYPE(array) != NPY_FLOAT32 || !PyArray_ISNOTSWAPPED(array)) {
        PyErr_SetString(PyExc_TypeError, "Expected native-endian float32.");
        return NULL;
    }
    int ndim = PyArray_NDIM(array);
    if ((ndim != 2 && ndim != 3) ||
        PyArray_DIM(array, ndim - 2) != self->height ||
        PyArray_DIM(array, ndim - 1) != self->width ||
        (ndim == 3 && PyArray_DIM(array, 0) < 1)) {
        PyErr_SetString(PyExc_ValueError, "Expected (height, width) or (batch, height, width), with batch >= 1.");
        return NULL;
    }
    if (!PyArray_IS_C_CONTIGUOUS(array) || !PyArray_ISALIGNED(array)) {
        PyErr_SetString(PyExc_ValueError, "Expected C-contiguous, float-aligned storage.");
        return NULL;
    }
    if (output && !PyArray_ISWRITEABLE(array)) {
        PyErr_SetString(PyExc_ValueError, "The output array must be writable.");
        return NULL;
    }
    return array;
}

static int apply_batch(Plan *self, int mode, npy_intp batch,
                       const float *input, float *output)
{
    for (npy_intp i = 0; i < batch; i++) {
        int status;
        if (mode == 2) {
            /* Match idct(dct(x)): the normalized spectrum is materialized. */
            status = bridct_plan_apply(self->kernel, BRIDCT_FORWARD, input, self->spectrum);
            if (!status)
                status = bridct_plan_apply(self->kernel, BRIDCT_INVERSE, self->spectrum, output);
        } else {
            status = bridct_plan_apply(self->kernel, (enum bridct_mode)mode, input, output);
        }
        if (status)
            return status;
        input += self->elements;
        output += self->elements;
    }
    return 0;
}

static PyObject *plan_execute(Plan *self, PyObject *const *args,
                              Py_ssize_t nargs, PyObject *keywords, int mode)
{
    if (!self->kernel) {
        PyErr_SetString(PyExc_RuntimeError, "This Plan is closed or uninitialized.");
        return NULL;
    }
    if (self->busy) {
        PyErr_SetString(PyExc_RuntimeError, "This Plan is executing in another thread; use one Plan per thread.");
        return NULL;
    }
    /* NumPy data allocators may invoke Python; protect setup as well as compute. */
    self->busy = 1;
    PyArrayObject *output = NULL;
    Py_ssize_t nkeys = keywords ? PyTuple_GET_SIZE(keywords) : 0;
    if (nargs != 1 || nkeys > 1) {
        PyErr_SetString(PyExc_TypeError, "Use method(input, *, out=None).");
        goto fail;
    }
    PyObject *out_object = Py_None;
    if (nkeys) {
        if (PyUnicode_CompareWithASCIIString(PyTuple_GET_ITEM(keywords, 0), "out") != 0) {
            PyErr_SetString(PyExc_TypeError, "The only accepted keyword is out.");
            goto fail;
        }
        out_object = args[1];
    }
    PyArrayObject *input = checked_array(args[0], self, 0);
    if (!input)
        goto fail;
    if (out_object == Py_None) {
        output = (PyArrayObject *)PyArray_SimpleNew(PyArray_NDIM(input), PyArray_DIMS(input), NPY_FLOAT32);
        if (!output)
            goto fail;
    } else {
        PyArrayObject *supplied = checked_array(out_object, self, 1);
        if (!supplied)
            goto fail;
        if (PyArray_NDIM(input) != PyArray_NDIM(supplied) ||
            PyArray_SIZE(input) != PyArray_SIZE(supplied)) {
            PyErr_SetString(PyExc_ValueError, "Input and output shapes must match exactly.");
            goto fail;
        }
        uintptr_t a = (uintptr_t)PyArray_DATA(input);
        uintptr_t b = (uintptr_t)PyArray_DATA(supplied);
        if ((a <= b ? b - a : a - b) < (size_t)PyArray_NBYTES(input)) {
            PyErr_SetString(PyExc_ValueError, "Input and output must not overlap.");
            goto fail;
        }
        output = supplied;
        Py_INCREF(output);
    }
    const float *x = PyArray_DATA(input);
    float *y = PyArray_DATA(output);
    npy_intp batch = PyArray_NDIM(input) == 3 ? PyArray_DIM(input, 0) : 1;
    int status;
    if (PyArray_SIZE(input) >= 16384) {
        /* The busy flag protects the plan while the GIL is released. */
        Py_BEGIN_ALLOW_THREADS
        status = apply_batch(self, mode, batch, x, y);
        Py_END_ALLOW_THREADS
    } else {
        status = apply_batch(self, mode, batch, x, y);
    }
    if (status) {
        PyErr_Format(PyExc_RuntimeError, "BRiDCT failed with status %d.", status);
        goto fail;
    }
    self->busy = 0;
    return (PyObject *)output;

fail:
    self->busy = 0;
    Py_XDECREF(output);
    return NULL;
}

static PyObject *plan_forward(Plan *self, PyObject *const *args, Py_ssize_t nargs, PyObject *keywords)
{
    return plan_execute(self, args, nargs, keywords, 0);
}

static PyObject *plan_inverse(Plan *self, PyObject *const *args, Py_ssize_t nargs, PyObject *keywords)
{
    return plan_execute(self, args, nargs, keywords, 1);
}

static PyObject *plan_roundtrip(Plan *self, PyObject *const *args, Py_ssize_t nargs, PyObject *keywords)
{
    return plan_execute(self, args, nargs, keywords, 2);
}

static PyObject *plan_shape(Plan *self, void *unused)
{
    (void)unused;
    return Py_BuildValue("(ii)", self->height, self->width);
}

static PyObject *plan_route(Plan *self, void *unused)
{
    (void)unused;
    if (!self->kernel)
        Py_RETURN_NONE;
    return PyUnicode_FromString(bridct_plan_route(self->kernel));
}

static PyObject *plan_closed(Plan *self, void *unused)
{
    (void)unused;
    return PyBool_FromLong(self->kernel == NULL);
}

#define METHOD_CAST(fn) (PyCFunction)(void (*)(void))(fn)
static PyMethodDef plan_methods[] = {
    {"forward", METHOD_CAST(plan_forward), METH_FASTCALL | METH_KEYWORDS,
     "forward(input, *, out=None): orthonormal 2D DCT-II over the last two axes."},
    {"inverse", METHOD_CAST(plan_inverse), METH_FASTCALL | METH_KEYWORDS,
     "inverse(input, *, out=None): orthonormal 2D DCT-III over the last two axes."},
    {"roundtrip", METHOD_CAST(plan_roundtrip), METH_FASTCALL | METH_KEYWORDS,
     "roundtrip(input, *, out=None): forward followed by inverse, with a materialized spectrum."},
    {"close", METHOD_CAST(plan_close), METH_NOARGS, "Release the native plan and its workspace."},
    {NULL, NULL, 0, NULL}
};

static PyGetSetDef plan_getsets[] = {
    {"shape", (getter)plan_shape, NULL, "Planned (height, width).", NULL},
    {"route", (getter)plan_route, NULL, "Native implementation route, or None when closed.", NULL},
    {"closed", (getter)plan_closed, NULL, "Whether the plan has been closed.", NULL},
    {NULL, NULL, NULL, NULL, NULL}
};

static PyTypeObject PlanType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "bridct_numpy.Plan",
    .tp_basicsize = sizeof(Plan),
    .tp_dealloc = (destructor)plan_dealloc,
    .tp_flags = Py_TPFLAGS_DEFAULT,
    .tp_doc = "Reusable orthonormal float32 DCT plan; one plan per concurrent worker.",
    .tp_methods = plan_methods,
    .tp_getset = plan_getsets,
    .tp_init = (initproc)plan_init,
    .tp_new = PyType_GenericNew
};

static int module_exec(PyObject *result)
{
    if (PyInterpreterState_Get() != PyInterpreterState_Main()) {
        PyErr_SetString(PyExc_ImportError, "bridct_numpy supports the main interpreter only.");
        return -1;
    }
    if (_import_array() < 0)
        return -1;
    if (PyType_Ready(&PlanType) < 0)
        return -1;
    if (PyModule_AddObjectRef(result, "Plan", (PyObject *)&PlanType) < 0 ||
        PyModule_AddStringConstant(result, "core_version", BRIDCT_VERSION) < 0)
        return -1;
    return 0;
}

/* CPython module slots require this callback-to-void-pointer conversion. */
#if defined(__GNUC__) && !defined(__clang__)
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wpedantic"
#endif
static PyModuleDef_Slot module_slots[] = {
    {Py_mod_exec, (void *)module_exec},
#if PY_VERSION_HEX >= 0x030C0000
    {Py_mod_multiple_interpreters, Py_MOD_MULTIPLE_INTERPRETERS_NOT_SUPPORTED},
#endif
    {0, NULL}
};
#if defined(__GNUC__) && !defined(__clang__)
#pragma GCC diagnostic pop
#endif

static PyModuleDef module = {
    PyModuleDef_HEAD_INIT,
    .m_name = "bridct_numpy",
    .m_doc = "Optional C11 CPython/NumPy interface to the standalone BRiDCT C library.",
    .m_size = 0,
    .m_slots = module_slots
};

PyMODINIT_FUNC PyInit_bridct_numpy(void)
{
    return PyModuleDef_Init(&module);
}
