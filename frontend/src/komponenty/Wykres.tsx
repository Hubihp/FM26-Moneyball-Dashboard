import type { EChartsOption } from 'echarts';
import { BarChart, LineChart, RadarChart, ScatterChart } from 'echarts/charts';
import {
  GridComponent,
  LegendComponent,
  RadarComponent,
  TooltipComponent,
  VisualMapComponent,
} from 'echarts/components';
import * as echarts from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { useEffect, useRef } from 'react';

// Tylko uzywane typy wykresow i komponenty - pakiet jest kilka razy mniejszy niz pelne ECharts
echarts.use([BarChart, LineChart, RadarChart, ScatterChart, GridComponent, LegendComponent, RadarComponent,
  TooltipComponent, VisualMapComponent, CanvasRenderer]);

type Props = { opcje: EChartsOption; wysokosc?: number | string; naKlik?: (dane: unknown) => void };

// Cienka otoczka na ECharts: tworzy wykres raz, aktualizuje opcje i reaguje na zmiane rozmiaru.
export default function Wykres({ opcje, wysokosc = 420, naKlik }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const wykres = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    wykres.current = echarts.init(ref.current, 'dark', { renderer: 'canvas' });
    const obserwator = new ResizeObserver(() => wykres.current?.resize());
    obserwator.observe(ref.current);
    return () => {
      obserwator.disconnect();
      wykres.current?.dispose();
      wykres.current = null;
    };
  }, []);

  useEffect(() => {
    wykres.current?.setOption({ backgroundColor: 'transparent', ...opcje }, true);
  }, [opcje]);

  useEffect(() => {
    const w = wykres.current;
    if (!w || !naKlik) return;
    const obsluga = (e: { data?: unknown }) => naKlik(e.data);
    w.on('click', obsluga);
    return () => {
      w.off('click', obsluga);
    };
  }, [naKlik]);

  return <div ref={ref} style={{ width: '100%', height: wysokosc }} />;
}
