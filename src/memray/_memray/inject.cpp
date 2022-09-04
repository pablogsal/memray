#define Py_LIMITED_API 0x03070000
#include "Python.h"

#include <netdb.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <sys/socket.h>
#include <sys/types.h>

#include <iostream>

namespace memray {
namespace {  // unnamed

int
connect_client(int port)
{
    struct addrinfo hints = {};
    struct addrinfo* all_addresses = nullptr;
    struct addrinfo* curr_address = nullptr;
    int rv;
    int sockfd;

    hints.ai_family = AF_UNSPEC;
    hints.ai_socktype = SOCK_STREAM;

    std::string port_str = std::to_string(port);
    if ((rv = ::getaddrinfo(nullptr, port_str.c_str(), &hints, &all_addresses)) != 0) {
        std::cerr << "getaddrinfo() failed while trying to attach Memray: " << ::gai_strerror(rv);
        return -1;
    }

    for (curr_address = all_addresses; curr_address != nullptr; curr_address = curr_address->ai_next) {
        sockfd = ::socket(curr_address->ai_family, curr_address->ai_socktype, curr_address->ai_protocol);
        if (sockfd == -1) {
            continue;
        }

        if (::connect(sockfd, curr_address->ai_addr, curr_address->ai_addrlen) == -1) {
            ::close(sockfd);
            continue;
        }
        break;
    }
    ::freeaddrinfo(all_addresses);
    if (curr_address == nullptr) {
        return -1;
    }
    return sockfd;
}

bool
sendall(int fd, std::string_view data)
{
    size_t length = data.size();
    while (length) {
        ssize_t ret = ::send(fd, &data[0], length, 0);
        if (ret < 0 && errno != EINTR) {
            return false;
        } else if (ret >= 0) {
            data.remove_prefix(ret);
            length -= ret;
        }
    }
    return true;
}

bool
recvall(int fd, std::string* data)
{
    data->clear();

    char buf[4096];
    while (true) {
        ssize_t ret = ::recv(fd, buf, sizeof(buf), 0);
        if (ret < 0 && errno != EINTR) {
            return false;
        } else if (ret > 0) {
            *data += std::string_view(buf, ret);
        } else if (ret == 0) {
            return true;
        }
    }
}

// Clear the error indicator, return a string representing the error.
std::string
Memray_PyErr_ToString()
{
    std::string ret;

    if (!PyErr_Occurred()) {
        return ret;
    }

    PyObject* type;
    PyObject* val;
    PyObject* tb;
    PyErr_Fetch(&type, &val, &tb);
    PyErr_NormalizeException(&type, &val, &tb);

    PyObject* exc_repr = PyObject_Repr(val);
    if (!exc_repr) {
        PyErr_Clear();
        ret = "unknown exception (`repr(exc)` failed)!";
    } else {
        PyObject* utf8 = PyUnicode_AsUTF8String(exc_repr);
        if (!utf8) {
            PyErr_Clear();
            ret = "unknown exception (`repr(exc).encode('utf-8')` failed)!";
        } else {
            ret = PyBytes_AsString(utf8);
        }
        Py_XDECREF(utf8);
    }
    Py_XDECREF(exc_repr);

    Py_XDECREF(type);
    Py_XDECREF(val);
    Py_XDECREF(tb);

    return ret;
}

bool
run_script_impl(const std::string& script, std::string* errmsg)
{
    int rc;

    PyObject* builtins = nullptr;
    PyObject* globals = nullptr;
    PyObject* code = nullptr;
    PyObject* mod = nullptr;
    bool success = false;

    builtins = PyImport_ImportModule("builtins");
    if (!builtins) {
        goto done;
    }

    globals = PyDict_New();
    if (!globals) {
        goto done;
    }

    // Needed on 3.7 to avoid ImportError('__import__ not found')
    rc = PyDict_SetItemString(globals, "__builtins__", builtins);
    if (0 != rc) {
        goto done;
    }

    code = Py_CompileString(script.data(), "_memray_attach_hook.py", Py_file_input);
    if (!code) {
        goto done;
    }

    mod = PyEval_EvalCode(code, globals, globals);
    if (!mod) {
        goto done;
    }

    success = true;

done:
    Py_XDECREF(mod);
    Py_XDECREF(code);
    Py_XDECREF(globals);
    Py_XDECREF(builtins);

    *errmsg = Memray_PyErr_ToString();
    return success;
}

bool
run_script(const std::string& script, std::string* errmsg)
{
    if (!Py_IsInitialized()) {
        *errmsg = "Python is not initialized";
        return false;
    }

    PyGILState_STATE gstate;
    gstate = PyGILState_Ensure();
    bool ret = run_script_impl(script, errmsg);
    PyGILState_Release(gstate);
    return ret;
}

void
run_client(int arg)
{
    int port = (intptr_t)arg;
    int sock = connect_client(port);
    if (sock == -1) {
        std::cerr << "memray attach failed!" << std::endl;
        return;
    }

    std::string script;
    if (!recvall(sock, &script)) {
        std::cerr << "memray attach socket read error!" << std::endl;
        return;
    }

    std::string errmsg;
    bool success = run_script(script.c_str(), &errmsg);

    if (!success) {
        sendall(sock, errmsg);
    }
    ::close(sock);
}

extern "C" void*
thread_body(void* arg)
{
    int rc = pthread_detach(pthread_self());
    if (0 != rc) {
        std::cerr << "Failed to detach thread!" << std::endl;
    }

    int port = reinterpret_cast<intptr_t>(arg);
    run_client(port);
    return nullptr;
}

}  // unnamed namespace

__attribute__((visibility("default"))) const char*
spawn_client(int port)
{
    // Running Python code directly in the point of attaching can lead to
    // crashes as we don't know if the interpreter is ready to execute code.
    // For instance, we can be in the middle of modifying the GC linked list
    // or doing some other operation that is not reentrant. Instead, we spawn
    // a new thread that will try to grab the GIL and run the code there.
    pthread_t thread;
    int rc = pthread_create(&thread, NULL, &thread_body, (void*)(intptr_t)port);
    if (0 != rc) {
        return "Failed to create thread!";
    }

    return nullptr;
}

}  // namespace memray
