#define PY_SSIZE_T_CLEAN
#define NPY_TARGET_VERSION NPY_1_22_API_VERSION
#define NPY_NO_DEPRECATED_API NPY_1_7_API_VERSION
#include <Python.h>
#include <numpy/arrayobject.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    PyDataMem_Handler handler;
    PyObject *callback;
    int fail, called;
} Hook;

static int invoke_hook(Hook *hook)
{
    if (hook->called)
        return 0;
    hook->called = 1;
    PyObject *result = PyObject_CallNoArgs(hook->callback);
    if (!result)
        return -1;
    Py_DECREF(result);
    return hook->fail ? -1 : 0;
}

static void *hook_malloc(void *context, size_t size)
{
    return invoke_hook(context) ? NULL : malloc(size);
}

static void *hook_calloc(void *context, size_t count, size_t size)
{
    return invoke_hook(context) ? NULL : calloc(count, size);
}

static void *hook_realloc(void *context, void *pointer, size_t size)
{
    return invoke_hook(context) ? NULL : realloc(pointer, size);
}

static void hook_free(void *context, void *pointer, size_t size)
{
    (void)context;
    (void)size;
    free(pointer);
}

static void hook_destroy(PyObject *capsule)
{
    Hook *hook = PyCapsule_GetPointer(capsule, "mem_handler");
    if (hook) {
        Py_DECREF(hook->callback);
        free(hook);
    }
}

static PyObject *run(PyObject *unused, PyObject *args)
{
    (void)unused;
    PyObject *operation, *callback;
    int fail = 0;
    if (!PyArg_ParseTuple(args, "OO|p:run", &operation, &callback, &fail))
        return NULL;
    Hook *hook = calloc(1, sizeof(*hook));
    if (!hook)
        return PyErr_NoMemory();
    strcpy(hook->handler.name, "bridct_test_allocator");
    hook->handler.version = 1;
    hook->handler.allocator.ctx = hook;
    hook->handler.allocator.malloc = hook_malloc;
    hook->handler.allocator.calloc = hook_calloc;
    hook->handler.allocator.realloc = hook_realloc;
    hook->handler.allocator.free = hook_free;
    hook->callback = Py_NewRef(callback);
    hook->fail = fail;
    PyObject *capsule = PyCapsule_New(hook, "mem_handler", hook_destroy);
    if (!capsule) {
        Py_DECREF(hook->callback);
        free(hook);
        return NULL;
    }
    PyObject *previous = PyDataMem_SetHandler(capsule);
    Py_DECREF(capsule);
    if (!previous)
        return NULL;
    PyObject *result = PyObject_CallNoArgs(operation);
    PyObject *error_type, *error_value, *error_traceback;
    PyErr_Fetch(&error_type, &error_value, &error_traceback);
    PyObject *current = PyDataMem_SetHandler(previous);
    Py_DECREF(previous);
    if (!current) {
        Py_XDECREF(error_type);
        Py_XDECREF(error_value);
        Py_XDECREF(error_traceback);
        Py_XDECREF(result);
        return NULL;
    }
    Py_DECREF(current);
    PyErr_Restore(error_type, error_value, error_traceback);
    return result;
}

static PyMethodDef methods[] = {
    {"run", run, METH_VARARGS, "Run with a one-shot NumPy allocation callback, optionally failing that allocation."},
    {NULL, NULL, 0, NULL}
};

static PyModuleDef module = {
    PyModuleDef_HEAD_INIT,
    .m_name = "bridct_test_allocator",
    .m_size = -1,
    .m_methods = methods
};

PyMODINIT_FUNC PyInit_bridct_test_allocator(void)
{
    import_array();
    return PyModule_Create(&module);
}
