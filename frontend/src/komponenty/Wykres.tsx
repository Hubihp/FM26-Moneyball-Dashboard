import type { EChartsOption } from 'echarts';
import { BarChart, LineChart, RadarChart, ScatterChart } from 'echarts/charts';
import {
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  RadarComponent,
  TooltipComponent,
  VisualMapComponent,
} from 'echarts/components';
import * as echarts from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { useEffect, useRef } from 'react';

import { useSkala } from '../powiekszenie';

// Tylko uzywane typy wykresow i komponenty - pakiet jest kilka razy mniejszy niz pelne ECharts
echarts.use([BarChart, LineChart, RadarChart, ScatterChart, GridComponent, LegendComponent, MarkLineComponent, RadarComponent,
  TooltipComponent, VisualMapComponent, CanvasRenderer]);

type Props = {
  opcje: EChartsOption; wysokosc?: number; naKlik?: (dane: unknown, indeks?: number) => void;
  // prawy przycisk na punkcie: dane punktu i zdarzenie myszy (menu zawodnika)
  naMenu?: (dane: unknown, e: MouseEvent) => void;
  // podswietlony punkt (indeks danych pierwszej serii): podpowiedz i wyroznienie, np. mecz wskazany w tabeli
  podswietl?: number | null;
};

// Cienka otoczka na ECharts: tworzy wykres raz, aktualizuje opcje i reaguje na zmiane rozmiaru.
// Na ukrytej karcie (React Activity) efekty sa zdejmowane, ale DOM zostaje - wykres nie jest wtedy niszczony,
// tylko podejmowany po powrocie (bez ponownego rysowania tysiecy punktow). Niszczony, gdy element znika z DOM.
//
// Powiekszenie interfejsu (CSS zoom na <html>) psulo wykresy: ECharts liczyl kursor w innych wspolrzednych niz
// rysunek (podpowiedz kilkaset pikseli obok kursora) i rysowal w nizszej rozdzielczosci. Dlatego wykres zyje
// w otoczce z odwrotnym zoomem (lacznie 1), a powiekszenie daje mu transform: scale - ECharts przelicza kursor
// przez transformacje poprawnie, a plotno ma rozdzielczosc ekranu x skala.
export default function Wykres({ opcje, wysokosc = 420, naKlik, naMenu, podswietl }: Props) {
  const skala = useSkala();
  const ref = useRef<HTMLDivElement>(null);
  const wykres = useRef<echarts.ECharts | null>(null);
  const narysowane = useRef<string | null>(null);     // klucz opcji obecnych na wykresie
  const skalaRef = useRef(skala);
  skalaRef.current = skala;

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const istniejacy = echarts.getInstanceByDom(el);
    if (!istniejacy) narysowane.current = null;
    wykres.current = istniejacy ?? echarts.init(el, 'dark', { renderer: 'canvas',
      devicePixelRatio: (window.devicePixelRatio || 1) * skala });
    // resize tylko przy faktycznej zmianie rozmiaru (kazde resize chowa podpowiedz)
    // (podjety wykres ma juz rozmiar - porownanie z nim, a nie z pustym napisem)
    const w0 = wykres.current;
    let rozmiar = istniejacy ? `${w0.getWidth()}x${w0.getHeight()}` : '';
    const obserwator = new ResizeObserver(([wpis]) => {
      const nowy = `${Math.round(wpis.contentRect.width)}x${Math.round(wpis.contentRect.height)}`;
      if (nowy !== rozmiar && wpis.contentRect.width > 0) {
        rozmiar = nowy;
        wykres.current?.resize();
      }
    });
    obserwator.observe(el);
    const instancja = wykres.current;
    return () => {
      obserwator.disconnect();
      wykres.current = null;
      // ukrycie karty: element zostaje w DOM; odmontowanie: element usuniety - wtedy dopiero dispose
      window.setTimeout(() => {
        if ((!el.isConnected || skalaRef.current !== skala) && !instancja.isDisposed()) instancja.dispose();
      }, 0);
    };
    // nowa skala: wykres tworzony od nowa (rozdzielczosc plotna)
  }, [skala]);

  // Opcje przychodza jako nowy obiekt przy kazdym renderze rodzica; setOption (bez scalania) kasuje wykres
  // i chowa podpowiedz, wiec wolamy go tylko przy faktycznej zmianie tresci (funkcje sa pomijane w kluczu)
  const klucz = JSON.stringify(opcje);
  const aktualne = useRef(opcje);
  aktualne.current = opcje;
  useEffect(() => {
    if (!wykres.current || narysowane.current === `${klucz}|${skala}`) return;
    narysowane.current = `${klucz}|${skala}`;
    const o = aktualne.current;
    try {
    wykres.current.setOption({
      backgroundColor: 'transparent', ...o,
      // podpowiedz w granicach wykresu: nie wydluza strony i nie wywoluje pasow przewijania
      tooltip: Array.isArray(o.tooltip) ? o.tooltip : { confine: true, ...(o.tooltip ?? {}) },
    }, true);
    } catch (e) {
      // blad konfiguracji wykresu nie moze wywrocic calej aplikacji
      console.warn('Wykres: nie udało się narysować', e);
    }
  }, [klucz, skala]);

  useEffect(() => {
    const w = wykres.current;
    // tylko wykresy z podswietlaniem (prop podany); null = zgas
    if (!w || w.isDisposed() || podswietl === undefined) return;
    try {
      w.dispatchAction({ type: 'downplay', seriesIndex: 0 });
      if (podswietl === null) {
        w.dispatchAction({ type: 'hideTip' });
        return;
      }
      w.dispatchAction({ type: 'highlight', seriesIndex: 0, dataIndex: podswietl });
      w.dispatchAction({ type: 'showTip', seriesIndex: 0, dataIndex: podswietl });
    } catch (e) {
      console.warn('Wykres: podświetlenie', e);
    }
  }, [podswietl, klucz, skala]);

  useEffect(() => {
    const w = wykres.current;
    if (!w || !naKlik) return;
    const obsluga = (e: { data?: unknown; dataIndex?: number }) => naKlik(e.data, e.dataIndex);
    w.on('click', obsluga);
    return () => {
      w.off('click', obsluga);
    };
  }, [naKlik, skala]);

  useEffect(() => {
    const w = wykres.current;
    if (!w || !naMenu) return;
    const obsluga = (e: { data?: unknown; event?: { event?: Event } }) => {
      const mysz = e.event?.event as MouseEvent | undefined;
      if (mysz) naMenu(e.data, mysz);
    };
    w.on('contextmenu', obsluga);
    return () => {
      w.off('contextmenu', obsluga);
    };
  }, [naMenu, skala]);

  // otoczka: zoom odwrotny do powiekszenia (lacznie 1), wysokosc jak dotad (wysokosc x skala na ekranie);
  // wykres: szerokosc 100% / skala i transform: scale(skala) - na ekranie dokladnie szerokosc otoczki
  return (
    <div style={{ zoom: 1 / skala, width: '100%', height: wysokosc * skala, overflow: 'hidden' }}>
      <div ref={ref} key={skala}
        style={{ width: `${100 / skala}%`, height: wysokosc, transform: `scale(${skala})`, transformOrigin: '0 0' }} />
    </div>
  );
}
