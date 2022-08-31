import { map, size } from "lodash";
import { initMemoryGraph, resizeMemoryGraph } from "./common";
window.resizeMemoryGraph = resizeMemoryGraph;

function main() {

var margin = {top: 10, right: 30, bottom: 30, left: 40},
    width = 1500 - margin.left - margin.right,
    height = 1000 - margin.top - margin.bottom;

// append the svg object to the body of the page
var svg = d3.select("#the_heatmap")
  .append("svg")
        .attr("style", "outline: thin solid black;")
    .attr("width", width + margin.left + margin.right)
    .attr("height", height + margin.top + margin.bottom)
  .append("g")
    .attr("transform",
          "translate(" + margin.left + "," + margin.top + ")");

// // Add X axis
//   var x = d3.scaleTime()
//     .domain(d3.extent(data, d => new Date(d.index ))).nice()
//     .rangeRound([margin.left, width - margin.right])
//   svg.append("g")
//     .attr("transform", "translate(0," + height + ")")
//     .call(d3.axisBottom(x));

//   // Add Y axis
//   var y = d3.scaleLog()
//     .domain(d3.extent(data, d=>d.size)).nice()
//     .rangeRound([height - margin.bottom, margin.top])
//   svg.append("g")
//     .call(d3.axisLeft(y));

//   // Prepare a color palette
//   var color = d3.scaleLinear()
//       .domain([0, 8]) // Points per square pixel.
//       .range(["white", "#69b3a2"])

//   // compute the density data
//   var densityData = d3.contourDensity()
//     .x(function(d) { return x(d.index); })
//     .y(function(d) { return y(d.size); })
//     .size([width, height])
//     .bandwidth(10)
//     (data)

//   // show the shape!
//   svg.insert("g", "g")
//     .selectAll("path")
//     .data(densityData)
//     .enter().append("path")
//       .attr("d", d3.geoPath())
//       .attr("fill", function(d) { return color(d.value); })


// Build X scales and axis:
var x = d3.scaleBand()
  .range([ 0, width ])
  .domain(data.map(d => d.time ))
  .padding(0.01);
svg.append("g")
  .attr("transform", "translate(0," + height + ")")
  .call(d3.axisBottom(x))

// Build X scales and axis:
var y = d3.scaleBand()
  .range([ height, 0 ])
  .domain(Array.from(Array(100).keys()))
  .padding(0.01);
svg.append("g")
  .call(d3.axisLeft(y));

// Build color scale
var myColor = d3.scaleLinear()
  .range(["white", "#69b3a2"])
  .domain([1, 1000]);
  
    svg.selectAll()
      .data(data)
      .enter()
      .append("rect")
      .attr("x", function(d) { return x(d.time) })
      .attr("y", function(d) { return y(d.bucket) })
      .attr("width", x.bandwidth() )
      .attr("height", y.bandwidth() )
      .style("fill", function(d) { return myColor(d.size)} )


}


document.addEventListener("DOMContentLoaded", main);
resizeMemoryGraph();