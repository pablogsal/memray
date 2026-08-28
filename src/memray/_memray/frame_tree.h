#pragma once
#include "internal_allocator.h"
#include "records.h"

namespace memray::tracking_api {
template<template<typename> typename Allocator = std::allocator>
class BasicFrameTree
{
  public:
    using index_t = size_t;

    inline index_t minIndex() const
    {
        return 1;
    }

    inline index_t maxIndex() const
    {
        return d_graph.size() - 1;
    }

    inline std::pair<frame_id_t, index_t> nextNode(index_t index) const
    {
        assert(1 <= index && index <= d_graph.size() - 1);
        return std::make_pair(d_graph[index].frame_id, d_graph[index].parent_index);
    }

    template<typename T, typename Callback>
    size_t getTraceIndex(const T& stack_trace, Callback&& callback)
    {
        index_t index = 0;
        for (const auto& frame : stack_trace) {
            index = getTraceIndexUnsafe(index, frame, callback);
        }
        return index;
    }

    size_t getTraceIndex(index_t parent_index, frame_id_t frame)
    {
        return getTraceIndexUnsafe(parent_index, frame, [](frame_id_t, index_t) { return true; });
    }

  private:
    template<typename Callback>
    size_t getTraceIndexUnsafe(index_t parent_index, frame_id_t frame, Callback&& callback)
    {
        Node& parent = d_graph[parent_index];
        auto it = std::lower_bound(parent.children.begin(), parent.children.end(), frame);
        if (it == parent.children.end() || it->frame_id != frame) {
            index_t new_index = d_graph.size();
            it = parent.children.insert(it, {frame, new_index});
            if (!callback(frame, parent_index)) {
                return 0;
            }
            d_graph.push_back({frame, parent_index});
        }
        return it->child_index;
    }

    struct DescendentEdge
    {
        frame_id_t frame_id;
        index_t child_index;

        bool operator<(frame_id_t the_frame_id) const
        {
            return this->frame_id < the_frame_id;
        }
    };

    struct Node
    {
        frame_id_t frame_id;
        index_t parent_index;
        std::vector<DescendentEdge, Allocator<DescendentEdge>> children;
    };
    std::vector<Node, Allocator<Node>> d_graph{{0, 0, {}}};
};

using FrameTree = BasicFrameTree<>;
using InternalFrameTree = BasicFrameTree<internal_allocator::Allocator>;
}  // namespace memray::tracking_api
