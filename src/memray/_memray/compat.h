#pragma once

#define PY_SSIZE_T_CLEAN
#include <Python.h>

#if PY_VERSION_HEX > 0x030C0000
#define Py_BUILD_CORE
#include "internal/pycore_object.h"
#undef Py_BUILD_CORE
#endif

#include "frameobject.h"

namespace memray::compat {

inline int
isPythonFinalizing()
{
#if PY_VERSION_HEX >= 0x030D0000
    return Py_IsFinalizing();
#else
    return _Py_IsFinalizing();
#endif
}

inline bool
isEntryFrame(PyFrameObject* frame)
{
#if PY_VERSION_HEX >= 0x030B0000
    return _PyFrame_IsEntryFrame(frame);
#else
    (void)frame;
    return true;
#endif
}

inline PyFrameObject*
threadStateGetFrame(PyThreadState* tstate)
{
#if PY_VERSION_HEX < 0x030B0000
    // Prior to Python 3.11 this was exposed.
    return tstate->frame;
#else
    // Return a borrowed reference.
    PyFrameObject* ret = PyThreadState_GetFrame(tstate);
    if (ret) {
        assert(Py_REFCNT(ret) >= 2);
        Py_DECREF(ret);
    }
    return ret;
#endif
}

inline PyCodeObject*
frameGetCode(PyFrameObject* frame)
{
#if PY_VERSION_HEX < 0x030B0000
    // Prior to Python 3.11 this was exposed.
    return frame->f_code;
#else
    // Return a borrowed reference.
    PyCodeObject* ret = PyFrame_GetCode(frame);
    assert(Py_REFCNT(ret) >= 2);
    Py_DECREF(ret);
    return ret;
#endif
}

inline PyFrameObject*
frameGetBack(PyFrameObject* frame)
{
#if PY_VERSION_HEX < 0x030B0000
    // Prior to Python 3.11 this was exposed.
    return frame->f_back;
#else
    // Return a borrowed reference.
    PyFrameObject* ret = PyFrame_GetBack(frame);
    if (ret) {
        assert(Py_REFCNT(ret) >= 2);
        Py_DECREF(ret);
    }
    return ret;
#endif
}

inline PyInterpreterState*
threadStateGetInterpreter(PyThreadState* tstate)
{
#if PY_VERSION_HEX < 0x03090000
    return tstate->interp;
#else
    return PyThreadState_GetInterpreter(tstate);
#endif
}

void
setprofileAllThreads(Py_tracefunc func, PyObject* arg);

typedef int (*refTracer)(PyObject*, int event, void *data);

inline int 
refTracerSetTracer(refTracer tracer, void *data) {
#if PY_VERSION_HEX >= 0x030D0000
    return PyRefTracer_SetTracer(reinterpret_cast<PyRefTracer>(tracer), data);
#else
    return nullptr;
#endif
}

inline size_t
pyType_PreHeaderSize(PyTypeObject *tp)
{
#if PY_VERSION_HEX >= 0x030C0000
    return _PyType_PreHeaderSize(tp);
#else
    return sizeof(PyGC_Head);
#endif

}

}  // namespace memray::compat
