import React, { useEffect, useRef, useMemo } from "react";
import PropTypes from "prop-types";
import * as echarts from "echarts";
import useChartResize from "./useChartResize";
import { Line, StackLine } from "akvo-charts";

const DEFAULT_COLORS = ["#1890ff", "#64A73B", "#F5A623", "#e41a1c", "#9b59b6"];

const CategoryLine = ({ config, data }) => {
  const boxRef = useRef(null);
  const chartRef = useRef(null);
  const chartData = useMemo(() => (Array.isArray(data) ? data : []), [data]);

  const option = useMemo(() => {
    const wc = config?.config || {};
    const colors = wc.chart_colors || DEFAULT_COLORS;
    const catColors = wc.category_colors || {};
    const labels = wc.stackMapping?.stack || [];
    if (chartData.length === 0 || labels.length === 0) {
      return null;
    }
    const seriesColors = labels.map(
      (name, idx) => catColors[name] || colors[idx % colors.length]
    );
    return {
      color: seriesColors,
      tooltip: {
        trigger: "axis",
        appendToBody: true,
      },
      legend: {
        data: labels,
        bottom: 0,
      },
      grid: { top: 20, right: 20, bottom: 40, left: 40, containLabel: true },
      xAxis: {
        type: "category",
        data: chartData.map((d) => d.label),
      },
      yAxis: {
        type: "value",
      },
      series: labels.map((name, idx) => ({
        name,
        type: "line",
        data: chartData.map((d) => d[name] ?? 0),
        itemStyle: { color: seriesColors[idx] },
      })),
    };
  }, [chartData, config]);

  useEffect(() => {
    const box = boxRef.current;
    if (!box || !option) {
      return () => {};
    }

    if (!chartRef.current) {
      chartRef.current = echarts.init(box);
    }
    chartRef.current.setOption(option, true);

    let cleanup;
    if (typeof ResizeObserver !== "undefined") {
      const observer = new ResizeObserver(() => {
        if (chartRef.current) {
          chartRef.current.resize();
        }
      });
      observer.observe(box);
      cleanup = () => observer.disconnect();
    } else {
      const sync = () => {
        if (chartRef.current) {
          chartRef.current.resize();
        }
      };
      window.addEventListener("resize", sync);
      cleanup = () => window.removeEventListener("resize", sync);
    }

    return () => {
      cleanup();
      if (chartRef.current) {
        chartRef.current.dispose();
        chartRef.current = null;
      }
    };
  }, [option]);

  if (chartData.length === 0) {
    return (
      <div style={{ padding: 16, color: "#999", textAlign: "center" }}>
        No data
      </div>
    );
  }

  return <div ref={boxRef} style={{ width: "100%", height: "100%" }} />;
};

const VizLine = ({ config, data }) => {
  const { chartRef, boxRef } = useChartResize();
  const widgetConfig = config?.config || {};
  const hasCategory = Boolean(widgetConfig.category_question_id);
  const hasStack = Boolean(widgetConfig.stack_by);

  if (hasCategory) {
    return <CategoryLine config={config} data={data} />;
  }

  const Component = hasStack ? StackLine : Line;

  const colors = Array.isArray(config?.color)
    ? config.color
    : widgetConfig.chart_colors || DEFAULT_COLORS;

  const chartConfig = { title: "", color: colors };
  const chartData = Array.isArray(data) ? data : [];

  if (chartData.length === 0) {
    return (
      <div style={{ padding: 16, color: "#999", textAlign: "center" }}>
        No data
      </div>
    );
  }

  const props = { config: chartConfig, data: chartData };
  if (hasStack && widgetConfig.stackMapping) {
    props.stackMapping = widgetConfig.stackMapping;
  }

  return (
    <div ref={boxRef} style={{ width: "100%", height: "100%" }}>
      <Component ref={chartRef} {...props} />
    </div>
  );
};

VizLine.propTypes = {
  config: PropTypes.object.isRequired,
  data: PropTypes.array,
};

export default VizLine;
