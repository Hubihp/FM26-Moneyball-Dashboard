import * as echarts from 'echarts';
import { useEffect, useRef } from 'react';

type Props = { opcje: echarts.EChartsOption; wysokosc?: number | string; naKlik?: (dane: unknown) => void };

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
