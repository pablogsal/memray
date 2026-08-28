#pragma once

#include <cstddef>
#include <cstdlib>
#include <limits>
#include <memory>
#include <new>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <type_traits>
#include <vector>

namespace memray::internal_allocator {

void*
allocate(size_t size, size_t alignment);

void
deallocate(void* ptr) noexcept;

void
afterFork();

template<typename T>
T*
construct()
{
    static_assert(std::is_nothrow_default_constructible_v<T>);
#ifdef __linux__
    void* storage = internal_allocator::allocate(sizeof(T), alignof(T));
    return new (storage) T;
#else
    return new T;
#endif
}

template<typename T>
void
destroy(T* ptr) noexcept
{
    if (!ptr) {
        return;
    }
#ifdef __linux__
    ptr->~T();
    internal_allocator::deallocate(ptr);
#else
    delete ptr;
#endif
}

#ifdef __linux__
template<typename T>
class Allocator
{
  public:
    using value_type = T;

    Allocator() noexcept = default;

    template<typename U>
    Allocator(const Allocator<U>&) noexcept
    {
    }

    T* allocate(size_t count)
    {
        if (count > std::numeric_limits<size_t>::max() / sizeof(T)) {
            std::abort();
        }
        return static_cast<T*>(internal_allocator::allocate(count * sizeof(T), alignof(T)));
    }

    void deallocate(T* ptr, size_t) noexcept
    {
        internal_allocator::deallocate(ptr);
    }

    template<typename U>
    bool operator==(const Allocator<U>&) const noexcept
    {
        return true;
    }

    template<typename U>
    bool operator!=(const Allocator<U>&) const noexcept
    {
        return false;
    }
};
#else
template<typename T>
using Allocator = std::allocator<T>;
#endif

using String = std::basic_string<char, std::char_traits<char>, Allocator<char>>;

template<typename T>
using Vector = std::vector<T, Allocator<T>>;

template<
        typename Key,
        typename Value,
        typename Hash = std::hash<Key>,
        typename Equal = std::equal_to<Key>>
using UnorderedMap =
        std::unordered_map<Key, Value, Hash, Equal, Allocator<std::pair<const Key, Value>>>;

template<typename Key, typename Hash = std::hash<Key>, typename Equal = std::equal_to<Key>>
using UnorderedSet = std::unordered_set<Key, Hash, Equal, Allocator<Key>>;

}  // namespace memray::internal_allocator
