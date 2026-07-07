"use client";

import { createChart, ColorType, type IChartApi } from "lightweight-charts";
import { useEffect, useRef } from "react";

const data = [
  { time: "2026-01-01", value: 126000 },
  { time: "2026-02-01", value: 131500 },
  { time: "2026-03-01", value: 128400 },
  { time: "2026-04-01", value: 142800 },
  { time: "2026-05-01", value: 151200 },
  { time: "2026-06-01", value: 158700 },
  { time: "2026-07-01", value: 163525 }
];

export function PortfolioChart() {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      height: 280,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#8B97A7"
      },
      grid: {
        vertLines: { color: "rgba(255,255,255,0.06)" },
        horzLines: { color: "rgba(255,255,255,0.06)" }
      },
      rightPriceScale: { borderColor: "rgba(255,255,255,0.10)" },
      timeScale: { borderColor: "rgba(255,255,255,0.10)" },
      handleScroll: {
        mouseWheel: false,
        pressedMouseMove: false,
        horzTouchDrag: false,
        vertTouchDrag: false
      },
      handleScale: {
        axisPressedMouseMove: false,
        mouseWheel: false,
        pinch: false
      }
    });
    const series = chart.addAreaSeries({
      lineColor: "#38BDF8",
      topColor: "rgba(56,189,248,0.35)",
      bottomColor: "rgba(56,189,248,0.02)"
    });
    series.setData(data);
    chart.timeScale().fitContent();
    chartRef.current = chart;

    const resize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    resize();
    window.addEventListener("resize", resize);
    return () => {
      window.removeEventListener("resize", resize);
      chart.remove();
    };
  }, []);

  return <div ref={containerRef} className="h-[280px] w-full touch-pan-y" />;
}
