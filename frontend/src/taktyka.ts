// Tablica taktyczna: formacje (pozycje aplikacji na pionowym boisku) i ukladanie najlepszej XI.
// Wspolrzedne w % boiska: x od lewej do prawej, y od gory (bramka rywala) do dolu (moja bramka).
import type { TaktykaZGry, ZawodnikSkladu } from './api';

export type Miejsce = { pozycja: string; x: number; y: number };
// bez: miejsce slotu bez pilki w ukladzie formacji (brak = broni tam, gdzie gra z pilka)
export type Slot = { id: string; pozycja: string; x: number; y: number; bez?: Miejsce };
// linie: wysokosc linii obrony i linii pressingu (y w % boiska) - ustawiane recznie na boisku bez pilki
export type Linie = { obrona: number; pressing: number };
export type Ustawienie = { formacja: string; sloty: Slot[]; przypisania: Record<string, string>; linie?: Linie };
export type Faza = 'z' | 'bez';

export const LINIE_DOMYSLNE: Linie = { obrona: 72, pressing: 38 };
export const ZAKRES_LINII = { obrona: [60, 86], pressing: [18, 52], odstep: 27 } as const;
const Y_NAPAD = 15;     // rzad napastnikow w ukladzie formacji
const Y_OBRONA = 76;    // rzad stoperow

export const miejsceBez = (s: Slot): Miejsce => s.bez ?? { pozycja: s.pozycja, x: s.x, y: s.y };

// Uklad formacji -> blok obronny: stoperzy na linii obrony, napastnicy na linii pressingu, reszta proporcjonalnie.
// Bramkarz zostaje w bramce.
export function naBlok(pozycja: string, y: number, linie: Linie): number {
  if (pozycja === 'Bramkarz') return y;
  const w = linie.pressing + ((y - Y_NAPAD) / (Y_OBRONA - Y_NAPAD)) * (linie.obrona - linie.pressing);
  return Math.min(87, Math.max(5, w));
}

// odwrotnie: punkt boiska bez pilki -> y w ukladzie formacji (zapis po przeciagnieciu zetonu)
export function zBloku(pozycja: string, y: number, linie: Linie): number {
  if (pozycja === 'Bramkarz') return y;
  return Y_NAPAD + ((y - linie.pressing) / (linie.obrona - linie.pressing)) * (Y_OBRONA - Y_NAPAD);
}

// Miejsce zetonu na boisku w danej fazie
export function miejsceWFazie(s: Slot, faza: Faza, linie: Linie): Miejsce {
  if (faza === 'z') return { pozycja: s.pozycja, x: s.x, y: s.y };
  const m = miejsceBez(s);
  return { pozycja: m.pozycja, x: m.x, y: naBlok(m.pozycja, m.y, linie) };
}

// "Duch": miejsce z pilka przeniesione do bloku obronnego - poczatek strzalki przesuniecia
export const duchWBloku = (s: Slot, linie: Linie) => ({ x: s.x, y: naBlok(s.pozycja, s.y, linie) });

// Zawodnik bez pilki gra na innej pozycji albo wyraznie gdzie indziej niz z pilka
export function przesuniety(s: Slot): boolean {
  if (!s.bez) return false;
  return s.bez.pozycja !== s.pozycja || Math.abs(s.bez.x - s.x) > 4 || Math.abs(s.bez.y - s.y) > 4;
}

export function opisLinii(rodzaj: keyof Linie, y: number): string {
  if (rodzaj === 'obrona') {
    return y <= 65 ? 'bardzo wysoka' : y <= 70 ? 'wysoka' : y <= 76 ? 'standardowa' : y <= 81 ? 'niska' : 'bardzo niska';
  }
  return y <= 24 ? 'bardzo wysoka' : y <= 32 ? 'wysoka' : y <= 43 ? 'średnia' : 'niska';
}

// Linie w dozwolonym zakresie, z minimalnym odstepem (blok nie moze sie zapasc)
export function ograniczLinie(l: Linie, ruszana: keyof Linie): Linie {
  const o = ZAKRES_LINII;
  let obrona = Math.min(o.obrona[1], Math.max(o.obrona[0], l.obrona));
  let pressing = Math.min(o.pressing[1], Math.max(o.pressing[0], l.pressing));
  if (obrona - pressing < o.odstep) {
    if (ruszana === 'obrona') pressing = Math.max(o.pressing[0], obrona - o.odstep);
    else obrona = Math.min(o.obrona[1], pressing + o.odstep);
    if (obrona - pressing < o.odstep) {
      if (ruszana === 'obrona') obrona = pressing + o.odstep;
      else pressing = obrona - o.odstep;
    }
  }
  return { obrona: Math.round(obrona * 10) / 10, pressing: Math.round(pressing * 10) / 10 };
}

export const SKROTY: Record<string, string> = {
  'Bramkarz': 'BR', 'Środkowy Obrońca': 'ŚO', 'Lewy Obrońca': 'LO', 'Prawy Obrońca': 'PO',
  'Lewy Wahadłowy': 'LWAH', 'Prawy Wahadłowy': 'PWAH', 'Defensywny Pomocnik': 'DP', 'Środkowy Pomocnik': 'ŚP',
  'Lewy Pomocnik': 'LP', 'Prawy Pomocnik': 'PP', 'Ofensywny Pomocnik': 'OP', 'Lewy Skrzydłowy': 'LS',
  'Prawy Skrzydłowy': 'PS', 'Napastnik': 'N',
};

const BR = ['Bramkarz', 50, 91] as const;
const CZWORKA = [['Lewy Obrońca', 14, 72], ['Środkowy Obrońca', 37, 76], ['Środkowy Obrońca', 63, 76],
  ['Prawy Obrońca', 86, 72]] as const;
const TROJKA = [['Środkowy Obrońca', 27, 76], ['Środkowy Obrońca', 50, 78], ['Środkowy Obrońca', 73, 76]] as const;

type Def = readonly (readonly [string, number, number])[];
const DEFINICJE: Record<string, Def> = {
  '4-3-3': [BR, ...CZWORKA, ['Defensywny Pomocnik', 50, 61], ['Środkowy Pomocnik', 31, 49], ['Środkowy Pomocnik', 69, 49],
    ['Lewy Skrzydłowy', 15, 24], ['Napastnik', 50, 15], ['Prawy Skrzydłowy', 85, 24]],
  '4-2-3-1': [BR, ...CZWORKA, ['Defensywny Pomocnik', 37, 60], ['Defensywny Pomocnik', 63, 60],
    ['Lewy Skrzydłowy', 16, 33], ['Ofensywny Pomocnik', 50, 36], ['Prawy Skrzydłowy', 84, 33], ['Napastnik', 50, 15]],
  '4-4-2': [BR, ...CZWORKA, ['Lewy Pomocnik', 13, 48], ['Środkowy Pomocnik', 37, 52], ['Środkowy Pomocnik', 63, 52],
    ['Prawy Pomocnik', 87, 48], ['Napastnik', 37, 17], ['Napastnik', 63, 17]],
  '4-1-4-1': [BR, ...CZWORKA, ['Defensywny Pomocnik', 50, 62], ['Lewy Pomocnik', 13, 44], ['Środkowy Pomocnik', 37, 47],
    ['Środkowy Pomocnik', 63, 47], ['Prawy Pomocnik', 87, 44], ['Napastnik', 50, 15]],
  '4-3-1-2': [BR, ...CZWORKA, ['Defensywny Pomocnik', 50, 62], ['Środkowy Pomocnik', 29, 51], ['Środkowy Pomocnik', 71, 51],
    ['Ofensywny Pomocnik', 50, 35], ['Napastnik', 37, 16], ['Napastnik', 63, 16]],
  '3-5-2': [BR, ...TROJKA, ['Lewy Wahadłowy', 10, 50], ['Defensywny Pomocnik', 50, 61], ['Środkowy Pomocnik', 32, 47],
    ['Środkowy Pomocnik', 68, 47], ['Prawy Wahadłowy', 90, 50], ['Napastnik', 37, 16], ['Napastnik', 63, 16]],
  '3-4-3': [BR, ...TROJKA, ['Lewy Wahadłowy', 10, 52], ['Środkowy Pomocnik', 37, 55], ['Środkowy Pomocnik', 63, 55],
    ['Prawy Wahadłowy', 90, 52], ['Lewy Skrzydłowy', 18, 24], ['Napastnik', 50, 15], ['Prawy Skrzydłowy', 82, 24]],
  '5-3-2': [BR, ['Lewy Wahadłowy', 9, 66], ...TROJKA, ['Prawy Wahadłowy', 91, 66], ['Środkowy Pomocnik', 28, 50],
    ['Defensywny Pomocnik', 50, 56], ['Środkowy Pomocnik', 72, 50], ['Napastnik', 37, 17], ['Napastnik', 63, 17]],
  '5-4-1': [BR, ['Lewy Wahadłowy', 9, 67], ...TROJKA, ['Prawy Wahadłowy', 91, 67], ['Lewy Pomocnik', 14, 45],
    ['Środkowy Pomocnik', 38, 50], ['Środkowy Pomocnik', 62, 50], ['Prawy Pomocnik', 86, 45], ['Napastnik', 50, 16]],
};

export const FORMACJE = Object.keys(DEFINICJE);

export function slotyFormacji(formacja: string): Slot[] {
  return (DEFINICJE[formacja] ?? DEFINICJE['4-3-3']).map(([pozycja, x, y], i) => ({ id: `s${i}`, pozycja, x, y }));
}

// Taktyka odczytana z zapisu gry -> ustawienie tablicy (wspolrzedne slotow z gry, zawodnicy po uid)
export function zTaktykiGry(t: TaktykaZGry, znani: Set<string>): Ustawienie {
  const sloty: Slot[] = t.sloty.map((s) => ({
    id: `g${s.numer}`, pozycja: s.pozycja, x: s.x, y: s.y,
    ...(s.pozycja_bez && s.x_bez != null && s.y_bez != null
      ? { bez: { pozycja: s.pozycja_bez, x: s.x_bez, y: s.y_bez } } : {}),
  }));
  const przypisania: Record<string, string> = {};
  for (const s of t.sloty) if (s.uid && znani.has(s.uid)) przypisania[`g${s.numer}`] = s.uid;
  return { formacja: t.formacja, sloty, przypisania };
}

// SCORE zawodnika na pozycji (gdy jest w jej puli) albo null
export const wynikNa = (z: ZawodnikSkladu | undefined, pozycja: string) =>
  z && z.score[pozycja] !== undefined ? z.score[pozycja] : null;

// Zawodnik gra na pozycji naturalnie, gdy jest w jej puli (ocena >= 18 w grze); inaczej ocena 1-20
export const naturalny = (z: ZawodnikSkladu | undefined, pozycja: string) => wynikNa(z, pozycja) !== null;

// Optymalny przydzial (metoda wegierska, O(n^2 m)): maksymalna suma wartosci, kazdy wiersz do innej kolumny.
// wartosci: n wierszy (sloty) x m kolumn (zawodnicy), n <= m. Zwraca indeks kolumny dla kazdego wiersza.
function przydzial(wartosci: number[][]): number[] {
  const n = wartosci.length;
  const m = n ? wartosci[0].length : 0;
  const INF = 1e18;
  const u = new Array(n + 1).fill(0);
  const v = new Array(m + 1).fill(0);
  const p = new Array(m + 1).fill(0);
  const way = new Array(m + 1).fill(0);
  for (let i = 1; i <= n; i++) {
    p[0] = i;
    let j0 = 0;
    const minv = new Array(m + 1).fill(INF);
    const used = new Array(m + 1).fill(false);
    do {
      used[j0] = true;
      const i0 = p[j0];
      let delta = INF;
      let j1 = 0;
      for (let j = 1; j <= m; j++) {
        if (used[j]) continue;
        const cur = -wartosci[i0 - 1][j - 1] - u[i0] - v[j];
        if (cur < minv[j]) { minv[j] = cur; way[j] = j0; }
        if (minv[j] < delta) { delta = minv[j]; j1 = j; }
      }
      for (let j = 0; j <= m; j++) {
        if (used[j]) { u[p[j]] += delta; v[j] -= delta; } else minv[j] -= delta;
      }
      j0 = j1;
    } while (p[j0] !== 0);
    do { const j1 = way[j0]; p[j0] = p[j1]; j0 = j1; } while (j0);
  }
  const wynik = new Array(n).fill(-1);
  for (let j = 1; j <= m; j++) if (p[j]) wynik[p[j] - 1] = j - 1;
  return wynik;
}

// Najlepsza XI: przydzial maksymalizujacy sume SCORE na pozycjach (zawodnik na naturalnej pozycji);
// poza naturalna pozycja tylko gdy brakuje naturalnych - wtedy wedlug oceny pozycji z gry (1-20)
export function najlepszaXI(sloty: Slot[], zawodnicy: ZawodnikSkladu[]): Record<string, string> {
  if (!sloty.length || !zawodnicy.length) return {};
  const KARA = 1000;
  const wartosc = (s: Slot, z: ZawodnikSkladu) => {
    const w = wynikNa(z, s.pozycja);
    return w !== null ? w : (z.oceny[s.pozycja] ?? 0) - KARA;
  };
  // gdy zawodnikow jest mniej niz slotow - puste kolumny (nikt) z najnizsza wartoscia
  const kolumny: (ZawodnikSkladu | null)[] = [...zawodnicy];
  while (kolumny.length < sloty.length) kolumny.push(null);
  const macierz = sloty.map((s) => kolumny.map((z) => (z ? wartosc(s, z) : -10 * KARA)));
  const wybor = przydzial(macierz);
  const przypisania: Record<string, string> = {};
  sloty.forEach((s, i) => {
    const z = kolumny[wybor[i]];
    if (z) przypisania[s.id] = z.klucz;
  });
  return przypisania;
}

// Zmiana formacji: zawodnicy zostaja na slotach o tej samej pozycji (w kolejnosci), reszta wolna
export function zmienFormacje(stare: Ustawienie, formacja: string): Ustawienie {
  const sloty = slotyFormacji(formacja);
  const wolniWgPozycji: Record<string, string[]> = {};
  for (const s of stare.sloty) {
    const gracz = stare.przypisania[s.id];
    if (gracz) (wolniWgPozycji[s.pozycja] ??= []).push(gracz);
  }
  const przypisania: Record<string, string> = {};
  for (const s of sloty) {
    const gracz = wolniWgPozycji[s.pozycja]?.shift();
    if (gracz) przypisania[s.id] = gracz;
  }
  return { formacja, sloty, przypisania };
}

// Przypisanie zawodnika do slotu; gdy byl juz na innym slocie - zamiana z obecnym zawodnikiem tego slotu
export function przypisz(u: Ustawienie, slotId: string, gracz: string): Ustawienie {
  const przypisania = { ...u.przypisania };
  const poprzedniSlot = Object.keys(przypisania).find((k) => przypisania[k] === gracz);
  const obecny = przypisania[slotId];
  if (poprzedniSlot) {
    if (obecny) przypisania[poprzedniSlot] = obecny;
    else delete przypisania[poprzedniSlot];
  }
  przypisania[slotId] = gracz;
  return { ...u, przypisania };
}

export function zamienSloty(u: Ustawienie, a: string, b: string): Ustawienie {
  const przypisania = { ...u.przypisania };
  const [pa, pb] = [przypisania[a], przypisania[b]];
  if (pb) przypisania[a] = pb; else delete przypisania[a];
  if (pa) przypisania[b] = pa; else delete przypisania[b];
  return { ...u, przypisania };
}
