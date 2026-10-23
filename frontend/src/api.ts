// Typy i wywolania API serwera (fm_moneyball/serwer/api.py).

export type Opcje = {
  rodzaj_statystyk: 'league' | 'overall';
  min_minut: number;
  kurs_waluty: number;
  wszystkie_naturalne_pozycje: boolean;
  tylko_kluby_w_lidze: boolean;
};

export type Stan = {
  status: 'pusto' | 'wczytywanie' | 'gotowe' | 'blad';
  komunikat: string;
  wersja: number;
  zrodlo: { typ: 'brak' | 'folder' | 'plik' | 'demo'; folder: string | null; plik: string | null; sledz: boolean; opcje: Opcje };
  meta: {
    nazwa_zapisu?: string;
    plik?: string;
    data_gry?: string | null;
    moj_klub?: string | null;
    moj_klub_uid?: number | null;
    ostrzezenia?: string[];
    liczniki?: Record<string, number>;
    czas_odczytu_s?: number;
    wczytano?: string;
    demo?: boolean;
  };
  pozycje: Record<string, number>;
};

export type MetaPozycji = {
  pozycja: string;
  liczba: number;
  ligi: string[];
  nogi: string[];
  wiek: [number, number] | null;
  cena_max: number | null;
  minuty_max: number | null;
  wagi_domyslne: Record<string, number>;
  ma_kontrakty: boolean;
  ma_ukryte: boolean;
};

export type Filtry = {
  ligi: string[];
  nogi: string[];
  wiek: [number, number] | null;
  cena: [number | null, number | null] | null;
  bez_ceny: boolean;
  szukaj: string;
  kontrakt_mies: number | null;
  min_minut: number;
  bez_mojego_klubu: boolean;
};

export type ZapytanieRankingu = {
  pozycja: string;
  wagi: Record<string, number> | null;
  ignoruj_mnoznik: boolean;
  k_baza: number;
  filtry: Filtry;
  pokaz_ukryte: boolean;
};

export type Format = 'score' | 'pasek' | 'int' | 'dec1' | 'dec2' | 'eur' | 'eur_tyg' | 'data' | 'tekst';
export type Kolumna = { naglowek: string; pole: string; format: Format; statystyka: boolean; nizsze_lepsze: boolean };
export type Wiersz = Record<string, string | number | boolean | null>;

export type Ranking = {
  kolumny: Kolumna[];
  wiersze: Wiersz[];
  liczba: number;
  liczba_wszystkich: number;
  pominiete: string[];
  statystyki: string[];
};

export type Radar = { etykiety: string[]; seria: { id: string; percentyle: number[]; wartosci: (number | null)[] }[] };

export type Zapisy = {
  folder: string | null;
  domyslny: string | null;
  kandydaci: string[];
  pliki: { nazwa: string; sciezka: string; rozmiar_mb: number; zmieniony: number }[];
};

async function zadanie<T>(url: string, init?: RequestInit): Promise<T> {
  const odp = await fetch(url, init);
  if (!odp.ok) {
    let tresc = `${odp.status} ${odp.statusText}`;
    try {
      const json = await odp.json();
      if (json?.detail) tresc = typeof json.detail === 'string' ? json.detail : JSON.stringify(json.detail);
    } catch {
      /* odpowiedz bez JSON */
    }
    throw new Error(tresc);
  }
  return odp.json() as Promise<T>;
}

const post = <T,>(url: string, body: unknown) =>
  zadanie<T>(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

export const api = {
  stan: () => zadanie<Stan>('/api/stan'),
  zapisy: (folder?: string | null) =>
    zadanie<Zapisy>('/api/zapisy' + (folder ? `?folder=${encodeURIComponent(folder)}` : '')),
  ustawZrodlo: (body: { typ: string; folder?: string | null; plik?: string | null; sledz?: boolean; opcje?: Opcje }) =>
    post<Stan>('/api/zrodlo', body),
  przeladuj: () => post<Stan>('/api/przeladuj', {}),
  metaPozycji: (pozycja: string) => zadanie<MetaPozycji>(`/api/pozycja/${encodeURIComponent(pozycja)}`),
  ranking: (body: ZapytanieRankingu) => post<Ranking>('/api/ranking', body),
  radar: (pozycja: string, ids: string[]) => post<Radar>('/api/radar', { pozycja, ids }),
  podobni: (body: ZapytanieRankingu & { id: string; n: number }) => post<{ wiersze: Wiersz[] }>('/api/podobni', body),
  nazwyLig: async (pliki: File[]) => {
    const dane = new FormData();
    pliki.forEach((p) => dane.append('pliki', p));
    return zadanie<{ rozpoznane: Record<string, string> }>('/api/nazwy-lig', { method: 'POST', body: dane });
  },
};

// Wgrywanie duzego pliku .fm z postepem (fetch nie raportuje postepu wysylania).
export function wgrajZapis(plik: File, naPostep: (proc: number) => void): Promise<Stan> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/wgraj');
    xhr.upload.onprogress = (e) => e.lengthComputable && naPostep(Math.round((e.loaded / e.total) * 100));
    xhr.onload = () => {
      try {
        const json = JSON.parse(xhr.responseText);
        if (xhr.status >= 200 && xhr.status < 300) resolve(json);
        else reject(new Error(json?.detail ?? `Błąd ${xhr.status}`));
      } catch {
        reject(new Error(`Błąd ${xhr.status}`));
      }
    };
    xhr.onerror = () => reject(new Error('Błąd połączenia z serwerem'));
    const dane = new FormData();
    dane.append('plik', plik);
    xhr.send(dane);
  });
}
