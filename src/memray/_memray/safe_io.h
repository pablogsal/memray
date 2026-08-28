#pragma once

#include <cerrno>
#include <cstddef>
#include <unistd.h>

namespace memray {

template<size_t N>
void
safeWriteStderr(const char (&message)[N]) noexcept
{
    size_t written = 0;
    while (written < N - 1) {
        ssize_t result = ::write(STDERR_FILENO, message + written, N - 1 - written);
        if (result > 0) {
            written += static_cast<size_t>(result);
        } else if (result < 0 && errno == EINTR) {
            continue;
        } else {
            break;
        }
    }
}

}  // namespace memray
