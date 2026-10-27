import type { Format } from './api';

export function eur(x: number | null | undefined): string {
  if (x === null || x === undefined || Number.isNaN(x)) return '–';
  if (x >= 1_000_000) return `${(x / 1_000_000).toFixed(1).replace('.', ',').replace(',0', '')} mln €`;
  if (x >= 1_000) return `${Math.round(x / 1_000)} tys. €`;
  return `${Math.round(x)} €`;
}

export function formatuj(wartosc: unknown, format: Format): string {
  if (wartosc === null || wartosc === undefined || wartosc === '') return '–';
  if (typeof wartosc !== 'number') {
    if (format === 'data' && typeof wartosc === 'string') {
      const [r, m, d] = wartosc.split('-');
      return `${Number(d)}.${Number(m)}.${r}`;
    }
    return String(wartosc);
  }
  switch (format) {
    case 'score':
    case 'int':
      return Math.round(wartosc).toString();
    case 'pasek':
      return `${Math.round(wartosc)}%`;
    case 'dec2':
      return wartosc.toFixed(2).replace('.', ',');
    case 'eur':
      return eur(wartosc);
    case 'mnoznik':
      return `×${wartosc.toFixed(1).replace('.', ',')}`;
    case 'eur_tyg':
      return `${eur(wartosc / 52)} / tydz.`;
    case 'zmiana':
      return `${wartosc > 0 ? '+' : ''}${wartosc.toFixed(1).replace('.', ',')}`;
    default:
      return wartosc.toFixed(1).replace('.', ',');
  }
}

// Kolor wyniku: czerwony (slaby) -> zolty -> zielony (mocny), skala T (50 = przecietny)
export function kolorWyniku(score: number): string {
  const t = Math.max(0, Math.min(1, (score - 30) / 40));
  const r = t < 0.5 ? 255 : Math.round(255 - (t - 0.5) * 2 * 102);
  const g = t < 0.5 ? Math.round(153 + t * 2 * 102) : 255;
  return `rgb(${r}, ${g}, 153)`;
}

// Kolor zmiany (rozwoj): zielony = wzrost, czerwony = spadek
export function kolorZmiany(x: number, prog = 2): string | undefined {
  if (x >= prog) return '#69db7c';
  if (x <= -prog) return '#ff8787';
  return undefined;
}

// Kolor niedowartosciowania (wycena wg wyniku / cena): zielony = tanszy, niz wynika z gry
export function kolorNiedowartosciowania(x: number): string | undefined {
  if (x >= 2) return '#69db7c';
  if (x >= 1.4) return '#b2f2bb';
  if (x <= 0.5) return '#ff8787';
  return undefined;
}
