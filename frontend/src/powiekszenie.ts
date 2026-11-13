// Powiekszenie calego interfejsu: Ctrl + kolko myszy (oraz Ctrl + "+" / "-" / "0").
// CSS zoom na <html> skaluje wszystko razem (tabele, wykresy, panele); skala zapamietana w pamieci programu.
import { useEffect, useRef, useState } from 'react';

import { usePamiec } from './pamiec';

export const SKALA_MIN = 0.6;
export const SKALA_MAX = 2;
const KROK = 0.1;

export const ograniczSkale = (s: number) =>
  Math.round(Math.min(SKALA_MAX, Math.max(SKALA_MIN, s)) * 100) / 100;

// Biezaca skala (do przeliczania wspolrzednych kursora na style elementow position: fixed)
export const skalaInterfejsu = () => parseFloat(document.documentElement.style.zoom || '1') || 1;

// -> [skala, widoczna plakietka "Powiększenie X%" (krotko po zmianie)]
export function usePowiekszenie(): [number, boolean] {
  const [skala, setSkala] = usePamiec('fm-powiekszenie', 1);
  const [plakietka, setPlakietka] = useState(false);
  const zegar = useRef<number | undefined>(undefined);
  const biezaca = useRef(skala);
  biezaca.current = skala;

  useEffect(() => {
    const s = String(ograniczSkale(skala));
    document.documentElement.style.zoom = s;
    // jednostki vh/dvh rosna razem z zoomem - wysokosci "na caly ekran" dziela przez --skala (style.css)
    document.documentElement.style.setProperty('--skala', s);
  }, [skala]);

  useEffect(() => {
    const zmien = (nowa: number) => {
      const s = ograniczSkale(nowa);
      if (s === biezaca.current) return;
      biezaca.current = s;         // kolejne zdarzenie kolka przed przerysowaniem liczy od nowej skali
      setSkala(s);
      setPlakietka(true);
      window.clearTimeout(zegar.current);
      zegar.current = window.setTimeout(() => setPlakietka(false), 1200);
    };
    const kolko = (e: WheelEvent) => {
      if (!e.ctrlKey) return;
      e.preventDefault();          // bez powiekszenia przegladarki (tryb w przegladarce)
      if (e.deltaY !== 0) zmien(biezaca.current + (e.deltaY < 0 ? KROK : -KROK));
    };
    const klawisz = (e: KeyboardEvent) => {
      if (!e.ctrlKey || e.altKey || e.metaKey) return;
      if (e.key === '+' || e.key === '=') zmien(biezaca.current + KROK);
      else if (e.key === '-' || e.key === '_') zmien(biezaca.current - KROK);
      else if (e.key === '0') zmien(1);
      else return;
      e.preventDefault();
    };
    window.addEventListener('wheel', kolko, { passive: false });
    window.addEventListener('keydown', klawisz);
    return () => {
      window.removeEventListener('wheel', kolko);
      window.removeEventListener('keydown', klawisz);
      window.clearTimeout(zegar.current);
    };
  }, [setSkala]);

  return [ograniczSkale(skala), plakietka];
}
