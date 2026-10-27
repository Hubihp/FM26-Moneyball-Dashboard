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
    // resize tylko przy faktycznej zmianie rozmiaru (kazde resize chowa podpowiedz)
    let rozmiar = '';
    const obserwator = new ResizeObserver(([wpis]) => {
      const nowy = `${Math.round(wpis.contentRect.width)}x${Math.round(wpis.contentRect.height)}`;
      if (nowy !== rozmiar) {
        rozmiar = nowy;
        wykres.current?.resize();
      }
    });
    obserwator.observe(ref.current);
    return () => {
      obserwator.disconnect();
      wykres.current?.dispose();
      wykres.current = null;
    };
  }, []);

  // Opcje przychodza jako nowy obiekt przy kazdym renderze rodzica; setOption (bez scalania) kasuje wykres
  // i chowa podpowiedz, wiec wolamy go tylko przy faktycznej zmianie tresci (funkcje sa pomijane w kluczu)
  const klucz = JSON.stringify(opcje);
  const aktualne = useRef(opcje);
  aktualne.current = opcje;
  useEffect(() => {
    const o = aktualne.current;
    wykres.current?.setOption({
      backgroundColor: 'transparent', ...o,
      // podpowiedz w granicach wykresu: nie wydluza strony i nie wywoluje pasow przewijania
      tooltip: Array.isArray(o.tooltip) ? o.tooltip : { confine: true, ...(o.tooltip ?? {}) },
    }, true);
  }, [klucz]);

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
