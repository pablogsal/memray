import {
  debounced,
  filterChildThreads,
  filterUninteresting,
  filterImportSystem,
  humanFileSize,
  makeTooltipString,
  sumAllocations,
} from "./common";

const FILTER_UNINTERESTING = "filter_uninteresting";
const FILTER_IMPORT_SYSTEM = "filter_import_system";
const FILTER_THREAD = "filter_thread";
let filteredChart = new FilteredChart();

// For navigable #[integer] fragments
function getCurrentId() {
  if (location.hash) {
    return parseInt(location.hash.substring(1), 10);
  } else {
    return 0;
  }
}

function updateZoomButtom() {
  document.getElementById("resetZoomButton").disabled = getCurrentId() == 0;
}

function onClick(d) {
  if (d.id == getCurrentId()) return;

  history.pushState({ id: d.id }, d.data.name, `#${d.id}`);
  updateZoomButtom();
}

function handleFragments() {
  const id = getCurrentId();
  const elem = chart.findById(id);
  if (!elem) return;

  chart.zoomTo(elem);
  updateZoomButtom();
}

// For the invert button
function onInvert() {
  chart.inverted(!chart.inverted());
  chart.resetZoom(); // calls onClick
}

function onResetZoom() {
  chart.resetZoom(); // calls onClick
}

// For window resizing
function getChartWidth() {
  // Figure out the width from window size
  const rem = parseFloat(getComputedStyle(document.documentElement).fontSize);
  return window.innerWidth - 2 * rem;
}

class FilteredChart {
  constructor() {
    this.filters = {};
  }
  registerFilter(name, func) {
    this.filters[name] = func;
  }
  unRegisterFilter(name) {
    delete this.filters[name];
  }

  drawChart(data) {
    let filtered = data;
    _.forOwn(this.filters, (func) => {
      filtered = func(filtered);
    });
    drawChart(filtered);
    // Merge 0 additional elements, triggering a redraw
    chart.merge([]);
  }
}

function onResize() {
  const width = getChartWidth();
  // Update element widths
  const svg = document.getElementById("chart").children[0];
  svg.setAttribute("width", width);
  chart.width(width);
  filteredChart.drawChart();
}

function onFilterThread() {
  const thread_id = this.dataset.thread;
  if (thread_id === "-0x1") {
    // Reset
    filteredChart.unRegisterFilter(FILTER_THREAD);
  } else {
    filteredChart.registerFilter(FILTER_THREAD, (data) => {
      let filteredData = filterChildThreads(data, thread_id);
      const totalAllocations = sumAllocations(filteredData.children);
      _.defaults(totalAllocations, filteredData);
      filteredData.n_allocations = totalAllocations.n_allocations;
      filteredData.value = totalAllocations.value;
      return filteredData;
    });
  }
  filteredChart.drawChart(data);
}

function onFilterUninteresting() {
  if (this.hideUninterestingFrames === undefined) {
    // Hide boring frames by default
    this.hideUninterestingFrames = true;
  }
  if (this.hideUninterestingFrames === true) {
    this.hideUninterestingFrames = true;

    filteredChart.registerFilter(FILTER_UNINTERESTING, (data) => {
      return filterUninteresting(data);
    });
  } else {
    filteredChart.unRegisterFilter(FILTER_UNINTERESTING);
  }
  this.hideUninterestingFrames = !this.hideUninterestingFrames;
  filteredChart.drawChart(data);
}

function onFilterImportSystem() {
  if (this.hideImportSystemFrames === undefined) {
    this.hideImportSystemFrames = true;
  }
  if (this.hideImportSystemFrames === true) {
    this.hideImportSystemFrames = true;

    filteredChart.registerFilter(FILTER_IMPORT_SYSTEM, (data) => {
      return filterImportSystem(data);
    });
  } else {
    filteredChart.unRegisterFilter(FILTER_IMPORT_SYSTEM);
  }
  this.hideImportSystemFrames = !this.hideImportSystemFrames;
  filteredChart.drawChart(data);
}

// For determining values for the graph
function getTooltip() {
  let tip = d3
    .tip()
    .attr("class", "d3-flame-graph-tip")
    .html((d) => {
      const totalSize = humanFileSize(d.data.value);
      return makeTooltipString(d.data, totalSize, merge_threads);
    })
    .direction((d) => {
      const midpoint = (d.x1 + d.x0) / 2;
      // If the midpoint is in a reasonable location, put it below the element.
      if (0.25 < midpoint && midpoint < 0.75) {
        return "s";
      }
      // We're far from the right
      if (d.x1 < 0.75) {
        return "e";
      }
      // We're far from the left
      if (d.x0 > 0.25) {
        return "w";
      }
      // This shouldn't happen reasonably? If it does, just put it above and
      // we'll deal with it later. :)
      return "n";
    });
  return tip;
}

// Our custom color mapping logic
function decimalHash(string) {
  let sum = 0;
  for (let i = 0; i < string.length; i++)
    sum += ((i + 1) * string.codePointAt(i)) / (1 << 8);
  return sum % 1;
}

function fileExtension(filename) {
  if (filename === undefined) return filename;
  return (
    filename.substring(filename.lastIndexOf(".") + 1, filename.length) ||
    filename
  );
}

function colorByExtension(extension) {
  if (extension == "py") {
    return d3.schemePastel1[2];
  } else if (extension == "c" || extension == "cpp" || extension == "h") {
    return d3.schemePastel1[5];
  } else {
    return d3.schemePastel1[8];
  }
}

function memrayColorMapper(d, originalColor) {
  // Highlighted nodes
  if (d.highlight) {
    return "orange";
  }
  // "builtin" / nodes that we don't want to highlight
  if (!d.data.name || !d.data.location) {
    return "#EEE";
  }

  return colorByExtension(fileExtension(d.data.location[1]));
}

// Show the 'Threads' dropdown if we have thread data, and populate it
function initThreadsDropdown(data, merge_threads) {
  if (merge_threads === true) {
    return;
  }
  const threads = data.unique_threads;
  if (!threads || threads.length <= 1) {
    return;
  }

  document.getElementById("threadsDropdown").removeAttribute("hidden");
  const threadsDropdownList = document.getElementById("threadsDropdownList");
  for (const thread of threads) {
    let elem = document.createElement("a");
    elem.className = "dropdown-item";
    elem.dataset.thread = thread;
    elem.text = thread;
    elem.onclick = onFilterThread;
    threadsDropdownList.appendChild(elem);
  }
}

function drawChart(chart_data) {
  chart = flamegraph()
    .width(getChartWidth())
    // smooth transitions
    .transitionDuration(250)
    .transitionEase(d3.easeCubic)
    // invert the graph by default
    .inverted(true)
    // make each row a little taller
    .cellHeight(20)
    // don't show elements that are less than 5px wide
    .minFrameSize(2)
    // set our custom handlers
    .setColorMapper(memrayColorMapper)
    .onClick(onClick)
    .tooltip(getTooltip());

  // Render the chart
  d3.select("#chart").datum(chart_data).call(chart);
}

export function initMemoryGraph(memory_records) {
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
  var debounce = null;
  document.getElementById("plot").on("plotly_relayout", function (event) {
    if (debounce) {
      clearTimeout(debounce);
    }

    debounce = setTimeout(function () {
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
    }, 500);
  });
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
}

var chart = null;
document.addEventListener("DOMContentLoaded", main);
