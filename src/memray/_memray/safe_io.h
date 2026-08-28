#pragma once

#include <cerrno>
#include <charconv>
#include <cstddef>
#include <string_view>
#include <type_traits>
#include <unistd.h>

namespace memray {

inline void
safeWriteStderr(std::string_view message) noexcept
{
    const int saved_errno = errno;
    size_t written = 0;
    while (written < message.size()) {
        ssize_t result = ::write(STDERR_FILENO, message.data() + written, message.size() - written);
        if (result > 0) {
            written += static_cast<size_t>(result);
        } else if (result < 0 && errno == EINTR) {
            continue;
        } else {
            break;
        }
    }
    errno = saved_errno;
}

template<size_t N>
void
safeWriteStderr(const char (&message)[N]) noexcept
{
    safeWriteStderr(std::string_view{message, N - 1});
}

template<typename Integer, std::enable_if_t<std::is_integral_v<Integer>, int> = 0>
void
safeWriteStderr(Integer value) noexcept
{
    char buffer[32];
    auto result = std::to_chars(buffer, buffer + sizeof(buffer), value);
    safeWriteStderr(std::string_view{buffer, static_cast<size_t>(result.ptr - buffer)});
}

template<typename... Parts>
void
safeWriteStderrParts(const Parts&... parts) noexcept
{
    (safeWriteStderr(parts), ...);
}

}  // namespace memray
