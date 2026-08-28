#include "internal_allocator.h"

#include <algorithm>
#include <atomic>
#include <cstdint>
#include <cstdlib>
#include <limits>
#include <memory_resource>
#include <mutex>
#include <new>
#include <sys/mman.h>
#include <sys/syscall.h>
#include <unistd.h>

namespace memray::internal_allocator {
namespace {

uintptr_t
alignUp(uintptr_t value, size_t alignment)
{
    return (value + alignment - 1) & ~(alignment - 1);
}

class MmapResource : public std::pmr::memory_resource
{
  private:
    struct MappingHeader
    {
        void* mapping;
        size_t size;
    };

    void* do_allocate(size_t bytes, size_t alignment) override
    {
        const size_t overhead = sizeof(MappingHeader) + alignment - 1;
        const size_t page_size = static_cast<size_t>(getpagesize());
        if (bytes > std::numeric_limits<size_t>::max() - overhead
            || bytes + overhead > std::numeric_limits<size_t>::max() - (page_size - 1))
        {
            std::abort();
        }

        const size_t mapping_size = alignUp(bytes + overhead, page_size);
        void* mapping = reinterpret_cast<void*>(
                syscall(SYS_mmap,
                        nullptr,
                        mapping_size,
                        PROT_READ | PROT_WRITE,
                        MAP_PRIVATE | MAP_ANONYMOUS | MAP_NORESERVE,
                        -1,
                        0));
        if (mapping == MAP_FAILED) {
            std::abort();
        }

        const uintptr_t address =
                alignUp(reinterpret_cast<uintptr_t>(mapping) + sizeof(MappingHeader), alignment);
        auto* header = reinterpret_cast<MappingHeader*>(address) - 1;
        *header = {mapping, mapping_size};
        return reinterpret_cast<void*>(address);
    }

    void do_deallocate(void* ptr, size_t, size_t) override
    {
        auto* header = reinterpret_cast<MappingHeader*>(ptr) - 1;
        syscall(SYS_munmap, header->mapping, header->size);
    }

    bool do_is_equal(const std::pmr::memory_resource& other) const noexcept override
    {
        return this == &other;
    }
};

using Pool = std::pmr::synchronized_pool_resource;

struct AllocationHeader
{
    Pool* pool;
    void* allocation;
    size_t allocation_size;
};

std::atomic<Pool*> s_pool{};
static_assert(decltype(s_pool)::is_always_lock_free);
std::mutex s_initialization_mutex;

MmapResource&
upstream()
{
    static MmapResource resource;
    return resource;
}

Pool*
createPool()
{
    MmapResource& resource = upstream();
    void* storage = resource.allocate(sizeof(Pool), alignof(Pool));
    std::pmr::pool_options options{};
    options.max_blocks_per_chunk = 64;
    options.largest_required_pool_block = 1024 * 1024;
    return new (storage) Pool(options, &resource);
}

Pool*
currentPool()
{
    Pool* pool = s_pool.load(std::memory_order_acquire);
    if (pool) {
        return pool;
    }

    std::lock_guard<std::mutex> lock(s_initialization_mutex);
    pool = s_pool.load(std::memory_order_relaxed);
    if (!pool) {
        pool = createPool();
        s_pool.store(pool, std::memory_order_release);
    }
    return pool;
}

}  // namespace

void*
allocate(size_t size, size_t alignment)
{
    alignment = std::max(alignment, alignof(std::max_align_t));
    if ((alignment & (alignment - 1)) != 0
        || size > std::numeric_limits<size_t>::max() - sizeof(AllocationHeader) - alignment)
    {
        std::abort();
    }

    Pool* pool = currentPool();
    const size_t allocation_size = std::max(size, size_t{1}) + sizeof(AllocationHeader) + alignment - 1;
    void* allocation = pool->allocate(allocation_size, alignof(std::max_align_t));
    const uintptr_t address =
            alignUp(reinterpret_cast<uintptr_t>(allocation) + sizeof(AllocationHeader), alignment);
    auto* header = reinterpret_cast<AllocationHeader*>(address) - 1;
    *header = {pool, allocation, allocation_size};
    return reinterpret_cast<void*>(address);
}

void
deallocate(void* ptr) noexcept
{
    if (!ptr) {
        return;
    }

    auto* header = reinterpret_cast<AllocationHeader*>(ptr) - 1;
    Pool* current_pool = s_pool.load(std::memory_order_acquire);
    if (header->pool == current_pool) {
        current_pool->deallocate(header->allocation, header->allocation_size, alignof(std::max_align_t));
    }
}

void
afterFork()
{
    // The old pool can contain a mutex held by a vanished thread. Its mappings
    // remain valid, while new allocations in the child use a fresh pool.
    s_pool.store(createPool(), std::memory_order_release);
}

}  // namespace memray::internal_allocator
