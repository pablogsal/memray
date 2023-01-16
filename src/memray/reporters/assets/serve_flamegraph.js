import {
  debounced,
} from "./common";

import {
  initThreadsDropdown,
  drawChart,
  handleFragments,
  onFilterUninteresting,
  onFilterImportSystem,
  onFilterThread,
  onResetZoom,
  onResize,
  onInvert,
} from "./flamegraph_common";

var ignore_calls = 0;

  // function to update the maximum point annotation
function updateMaxAnnotation(start_str, end_str) {
    const time = memory_records.map((a) => new Date(a[0]));
    const resident_size = memory_records.map((a) => a[1]);

    var start = new Date(start_str);
    var end = new Date(end_str);
    var range = Plotly.relayout("plot", { "xaxis.range": [start, end] });
    var filtered_data_x = time.filter((t) => t >= start && t <= end);
    var filtered_data_y = resident_size.filter((y, i) => time[i] >= start && time[i] <= end);
    var max_y = Math.max(...filtered_data_y);
    var max_x = filtered_data_x[filtered_data_y.indexOf(max_y)];

    ignore_calls += 1;
    Plotly.update("plot", {}, {
      annotations: [
        {
          x: max_x,
          y: max_y,
          xref: 'x',
          yref: 'y',
          text: 'High water mark',
          showarrow: true,
          arrowhead: 2,
          ax: -40,
          ay: -40
        }],
      shapes: [
        {
          type: 'line',
          x0: max_x,
          y0: 0,
          x1: max_x,
          y1: 1,
          xref: 'x',
          yref: 'paper',
          line: {
            color: 'rgb(50, 171, 96)',
            width: 2
          }
        }
      ],
    });
  }

function initMemoryGraph(memory_records) {
  const time = memory_records.map((a) => new Date(a[0]));
  const resident_size = memory_records.map((a) => a[1]);
  const heap_size = memory_records.map((a) => a[2]);

  var resident_size_plot = {
    x: time,
    y: resident_size,
    mode: "lines",
    name: "Resident size",
  };

  var heap_size_plot = {
    x: time,
    y: heap_size,
    mode: "lines",
    name: "Heap size",
  };

  var plot_data = [resident_size_plot, heap_size_plot];
  var config = {
    responsive: true,
  };
  var layout = {
    xaxis: {
      title: {
        text: "Time",
      },
      rangeslider: {
        visible: true,
      },
    },
    yaxis: {
      title: {
        text: "Memory Size",
      },
      tickformat: ".4~s",
      exponentformat: "B",
      ticksuffix: "B",
    },
  };

  Plotly.newPlot("plot", plot_data, layout, config);


  // Trigger an intial update of the max point annotation
  const start_str = new Date(Math.min.apply(null,time)).toISOString();
  const end_str = new Date(Math.max.apply(null,time)).toISOString();
  updateMaxAnnotation(start_str,end_str);
}



function refreshFlamegraph(event) {
  // Show the loading animation
  var request_data = {};
  if (event.hasOwnProperty("xaxis.range[0]")) {
    request_data = {
      string1: event["xaxis.range[0]"],
      string2: event["xaxis.range[1]"],
    };
  } else if (event.hasOwnProperty("xaxis.range")) {
    request_data = {
      string1: event["xaxis.range"][0],
      string2: event["xaxis.range"][1],
    };
  } else {
    return;
  }

  updateMaxAnnotation(request_data.string1, request_data.string2);

  document.getElementById("loading").style.display = "block";
  document.getElementById("overlay").style.display = "block";
  fetch("http://127.0.0.1:5000/time", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request_data),
  })
    .then((response) => response.json())
    .then((the_data) => {
      data = the_data["data"];
      drawChart(data);
      // Hide the loading animation
      document.getElementById("loading").style.display = "none";
      document.getElementById("overlay").style.display = "none";
    })
    .catch((error) => {
      console.error("Error rendering new data!");
      console.error(error);
      // Hide the loading animation
      document.getElementById("loading").style.display = "none";
      document.getElementById("overlay").style.display = "none";
    });
}

var debounce = null;
function refreshFlamegraphDebounced(event) {
  if (debounce) {
    clearTimeout(debounce);
  }
  if (ignore_calls > 0) {
    ignore_calls--;
    return;
  }
  debounce = setTimeout(function () {
    refreshFlamegraph(event);
  }, 500);
}


// Main entrypoint
function main() {
  initThreadsDropdown(data, merge_threads);

  initMemoryGraph(memory_records);

  // Create the flamegraph renderer
  drawChart(data);

  // Set zoom to correct element
  if (location.hash) {
    handleFragments();
  }

  // Setup event handlers
  document.getElementById("invertButton").onclick = onInvert;
  document.getElementById("resetZoomButton").onclick = onResetZoom;
  document.getElementById("resetThreadFilterItem").onclick = onFilterThread;
  let hideUninterestingCheckBox = document.getElementById("hideUninteresting");
  hideUninterestingCheckBox.onclick = onFilterUninteresting.bind(this);
  let hideImportSystemCheckBox = document.getElementById("hideImportSystem");
  hideImportSystemCheckBox.onclick = onFilterImportSystem.bind(this);
  // Enable filtering by default
  onFilterUninteresting.bind(this)();

  document.onkeyup = (event) => {
    if (event.code == "Escape") {
      onResetZoom();
    }
  };
  document.getElementById("searchTerm").addEventListener("input", () => {
    const termElement = document.getElementById("searchTerm");
    chart.search(termElement.value);
  });

  window.addEventListener("popstate", handleFragments);
  window.addEventListener("resize", debounced(onResize));

  // Enable tooltips
  $('[data-toggle-second="tooltip"]').tooltip();
  $('[data-toggle="tooltip"]').tooltip();

  // Set up the reload handler
  document.getElementById("plot").on("plotly_relayout", refreshFlamegraphDebounced);
}

document.addEventListener("DOMContentLoaded", main);
