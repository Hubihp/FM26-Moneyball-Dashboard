// Typy i wywolania API serwera (fm_moneyball/serwer/api.py).

export type Opcje = {
  rodzaj_statystyk: 'league' | 'overall';
  min_minut: number;
  kurs_waluty: number;
  wszystkie_naturalne_pozycje: boolean;
  tylko_kluby_w_lidze: boolean;
  wolni_agenci: boolean;
};

export type Klub = { uid: number; nazwa: string };

export type Stan = {
  status: 'pusto' | 'wczytywanie' | 'gotowe' | 'blad';
  komunikat: string;
  wersja: number;
  etap: { nr: number; z: number; nazwa: string; start: number } | null;
  zrodlo: {
    typ: 'brak' | 'folder' | 'plik' | 'demo';
    folder: string | null;
    plik: string | null;
    sledz: boolean;
    wczytaj_przy_starcie: boolean;
    opcje: Opcje;
  };
  meta: {
    nazwa_zapisu?: string;
    plik?: string;
    data_gry?: string | null;
    moj_klub?: string | null;
    moj_klub_uid?: number | null;
    moje_kluby?: Klub[];
    z_cache?: boolean;
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
  nogi: string[];
  wiek: [number, number] | null;
  cena_max: number | null;
  minuty_max: number | null;
  wagi_domyslne: Record<string, number>;
  ma_kontrakty: boolean;
  okazje: string[];
  ma_historie: boolean;
  data_porownania: string | null;
  min_minut_rozwoju: number;
};

export type PunktHistorii = {
  data: string;
  sezon: number;
  SCORE: number | null;
  Percentyl: number | null;
  Minuty: number | null;
  mala_proba: boolean; // mniej niz min_minut (1000) - dane z malej liczby minut
  Wartość: number | null;
  statystyki: Record<string, number | null>;
};
export type CechaPorownania = {
  nazwa: string;
  nizsze_lepsze: boolean;
  kandydat: number | null;
  moj: number | null;
  percentyl_kandydata: number | null;
  percentyl_moj: number | null;
  lepszy: 'kandydat' | 'moj' | null;
};
export type PorownanieZMoim = {
  moj: Wiersz | null;
  werdykt: 'wzmocnienie' | 'podobny poziom' | 'nie wzmacnia' | 'brak zawodnika' | 'twój zawodnik' | 'nieznany klub' | null;
  roznica: number | null;
  cechy: CechaPorownania[];
};
export type ZmianaSezonowa = {
  wartosc: number;
  wzgledem: string;
  minuty_wtedy: number | null;
  minuty_teraz: number | null;
  mala_proba: boolean;
};
export type Historia = {
  punkty: PunktHistorii[];
  statystyki: string[];
  min_minut: number;
  brak: string[]; // daty migawek bez zawodnika (np. ponizej progu wczytywania)
  delta: ZmianaSezonowa | null;
};
export type HistoriaWielu = {
  zawodnicy: (Omit<Historia, 'statystyki' | 'min_minut'> & { id: string; pilkarz: string | null; statystyki?: string[] })[];
  min_minut: number;
};

export type Filtry = {
  ligi: string[];
  nogi: string[];
  kraje: string[];
  wiek: [number, number] | null;
  cena: [number | null, number | null] | null;
  bez_ceny: boolean;
  szukaj: string;
  kontrakt_mies: number | null;
  min_minut: number;
  bez_mojego_klubu: boolean;
  okazje: string[];
  min_rozwoj: number | null; // zmiana SCORE wzgledem poprzedniego sezonu
  kandydaci: boolean;
  min_score_kandydata: number;
  min_niedowartosciowanie: number | null;
  tylko_z_okazja?: boolean;
  kandydaci_z: string[]; // pozycje, z ktorych pochodza kandydaci (puste = wszystkie)
};

export type ZapytanieRankingu = {
  pozycja: string;
  wagi: Record<string, number> | null;
  ignoruj_mnoznik: boolean;
  k_baza: number;
  filtry: Filtry;
};

export type Format = 'score' | 'pasek' | 'int' | 'dec1' | 'dec2' | 'eur' | 'eur_tyg' | 'data' | 'tekst' | 'mnoznik' | 'zmiana';

// Model ceny wg wyniku (fm_moneyball/wycena.py)
export type ModelWyceny = {
  r2: number | null;
  liczba: number;
  proc_za_10_score: number | null;
  proc_za_rok_mlodszy: number | null;
};
export type Kolumna = {
  naglowek: string;
  pole: string;
  format: Format;
  statystyka: boolean;
  nizsze_lepsze: boolean;
  sortuj?: boolean; // domyslne sortowanie tabeli (np. podobienstwo w "Nastepcy")
};
export type Wiersz = Record<string, string | number | boolean | null>;

export type Ranking = {
  pozycja: string;
  kolumny: Kolumna[];
  wiersze: Wiersz[];
  liczba: number;
  liczba_wszystkich: number;
  liczba_kandydatow: number;
  liczba_ukrytych_mojego_klubu: number;
  pominiete: string[];
  statystyki: string[];
  model_wyceny: ModelWyceny;
};

export type Radar = {
  etykiety: string[];
  seria: { id: string; pilkarz: string | null; percentyle: number[]; wartosci: (number | null)[] }[];
};

export type Zapisy = {
  folder: string | null;
  domyslny: string | null;
  kandydaci: string[];
  pliki: { nazwa: string; sciezka: string; rozmiar_mb: number; zmieniony: number }[];
};

export type Liga = {
  klucz: number | null;
  domyslna: string;
  nazwa: string | null;
  liczba: number;
  kluby: string[];
  mnoznik: number | null;
};
export type Ligi = { ligi: Liga[]; znane_nazwy: string[]; mnozniki: Record<string, number>; mnoznik_nieznanej: number };

export type PozycjaKadry = {
  pozycja: string;
  liczba: number;
  najlepszy: number | null;
  sredni_wiek: number | null;
  konczace_kontrakty: number;
  zawodnicy: Wiersz[];
};
export type Kadra = { klub: string | null; pozycje: PozycjaKadry[] };

export type Kraj = {
  id: number | null;
  nazwa: string | null;
  zrodlo: 'ręcznie' | 'liga' | 'kluby' | null;
  reczna: boolean;
  liczba: number;
  przyklady: string[];
};

export type SystemInfo = {
  wersja_programu: string;
  sprawdzono: boolean;
  dostepna: boolean;
  wersja: string | null;
  notatki: string | null;
  strona: string;
  rozmiar: number | null;
  mozna_instalowac: boolean;
  okno: boolean;
  postep: { etap: 'pobieranie' | 'instalacja' | 'blad'; proc?: number; komunikat?: string } | null;
};

export type ListaZyczen = { kolumny: Kolumna[]; wiersze: Wiersz[]; nieznalezieni: string[] };

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
  system: () => zadanie<SystemInfo>('/api/system'),
  sprawdzAktualizacje: () => post<SystemInfo>('/api/aktualizacja/sprawdz', {}),
  instalujAktualizacje: () => post<SystemInfo>('/api/aktualizacja/instaluj', {}),
  przeniesZPrzegladarki: () => post<{ ok: boolean }>('/api/przenies-z-przegladarki', {}),
  stan: () => zadanie<Stan>('/api/stan'),
  zapisy: (folder?: string | null) =>
    zadanie<Zapisy>('/api/zapisy' + (folder ? `?folder=${encodeURIComponent(folder)}` : '')),
  ustawZrodlo: (body: {
    typ: string;
    folder?: string | null;
    plik?: string | null;
    sledz?: boolean;
    wczytaj_przy_starcie?: boolean;
    opcje?: Opcje;
  }) => post<Stan>('/api/zrodlo', body),
  mojKlub: (uid: number) => post<Stan>('/api/moj-klub', { uid }),
  ligi: () => zadanie<Ligi>('/api/ligi'),
  zmienLige: (klucz: number, nazwa: string, mnoznik: number | null) =>
    zadanie<Ligi>(`/api/ligi/${klucz}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nazwa, mnoznik }),
    }),
  kraje: () => zadanie<{ kraje: Kraj[] }>('/api/kraje'),
  zmienKraj: (id: number, nazwa: string) =>
    zadanie<{ kraje: Kraj[] }>(`/api/kraje/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nazwa }),
    }),
  listaZyczen: (body: {
    wpisy: { klucz: string; pozycja: string; pilkarz: string }[];
    pozycja?: string; // kolumny jak w Rankingu tej pozycji
    wagi: Record<string, Record<string, number>>;
    ignoruj_mnoznik: boolean;
    k_baza: number;
  }) => post<ListaZyczen>('/api/lista-zyczen', body),
  mojaKadra: (body: { wagi: Record<string, Record<string, number>>; ignoruj_mnoznik: boolean; k_baza: number }) =>
    post<Kadra>('/api/moja-kadra', body),
  przeladuj: () => post<Stan>('/api/przeladuj', {}),
  metaPozycji: (pozycja: string) => zadanie<MetaPozycji>(`/api/pozycja/${encodeURIComponent(pozycja)}`),
  ranking: (body: ZapytanieRankingu) => post<Ranking>('/api/ranking', body),
  nastepca: (body: ZapytanieRankingu & { id: string; n?: number }) =>
    post<{ kolumny: Kolumna[]; wiersze: Wiersz[]; liczba_po_filtrach: number }>('/api/nastepca', body),
  porownanieZMoim: (body: ZapytanieRankingu & { id: string }) => post<PorownanieZMoim>('/api/porownanie-z-moim', body),
  historia: (body: { pozycja: string; id: string; wagi: Record<string, number> | null; ignoruj_mnoznik: boolean;
    k_baza: number }) => post<Historia>('/api/historia', body),
  historiaWielu: (body: { pozycja: string; ids: string[]; wagi: Record<string, number> | null; ignoruj_mnoznik: boolean;
    k_baza: number }) => post<HistoriaWielu>('/api/historia-wielu', body),
  radar: (pozycja: string, ids: string[], kandydaci = false) => post<Radar>('/api/radar', { pozycja, ids, kandydaci }),
  podobni: (body: ZapytanieRankingu & { id: string; n: number }) => post<{ wiersze: Wiersz[] }>('/api/podobni', body),
  nazwyLig: async (pliki: File[]) => {
    const dane = new FormData();
    pliki.forEach((p) => dane.append('pliki', p));
    return zadanie<{ rozpoznane: Record<string, string> }>('/api/nazwy-lig', { method: 'POST', body: dane });
  },
};

// Wgrywanie duzego pliku .fm z postepem (fetch nie raportuje postepu wysylania).
// Plik idzie surowo w ciele zapytania - serwer zapisuje go strumieniowo, bez multipart.
export function wgrajZapis(plik: File, naPostep: (proc: number) => void): Promise<Stan> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', `/api/wgraj?nazwa=${encodeURIComponent(plik.name)}`);
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
    xhr.setRequestHeader('Content-Type', 'application/octet-stream');
    xhr.send(plik);
  });
}
