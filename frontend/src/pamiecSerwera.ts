// Pamiec interfejsu (lista zyczen, filtry, wagi, ustawienia, uklad tabel) trzymana na serwerze
// w ~/.fm_moneyball/pamiec.json - wspolna dla okna programu i przegladarki, odporna na aktualizacje.
// localStorage jest tylko kopia zapasowa (gdy serwer nie odpowiada).
//
// Migracja: klucze "fm-*" z localStorage tej przegladarki, ktorych nie ma na serwerze, sa wysylane
// na serwer przy starcie. Adres z ?przenies=1 (przycisk "Przenies dane z przegladarki" w oknie
// programu) nadpisuje nimi dane serwera - tak dawna lista zyczen z przegladarki trafia do okna.

const PREFIKS = 'fm-';
let pamiec: Record<string, string> = {};
let serwerDostepny = false;
let oczekujace: Record<string, string | null> = {};
let licznik: ReturnType<typeof setTimeout> | undefined;

export type WynikWczytania = { przeniesiono: number; wymuszone: boolean; pustaNaSerwerze: boolean };
export let wynikWczytania: WynikWczytania = { przeniesiono: 0, wymuszone: false, pustaNaSerwerze: false };

function kluczeLokalne(): Record<string, string> {
  const wynik: Record<string, string> = {};
  try {
    for (let i = 0; i < window.localStorage.length; i++) {
      const k = window.localStorage.key(i);
      if (k?.startsWith(PREFIKS)) wynik[k] = window.localStorage.getItem(k) ?? '';
    }
  } catch {
    /* localStorage zablokowany */
  }
  return wynik;
}

async function wyslij(zmiany: Record<string, string | null>, keepalive = false) {
  if (!serwerDostepny || !Object.keys(zmiany).length) return;
  try {
    await fetch('/api/pamiec', {
      method: 'PUT', keepalive, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ zmiany }),
    });
  } catch {
    /* serwer zamkniety - zostaje kopia w localStorage */
  }
}

function wyslijOczekujace(keepalive = false) {
  clearTimeout(licznik);
  const zmiany = oczekujace;
  oczekujace = {};
  void wyslij(zmiany, keepalive);
}

export async function wczytajPamiec(): Promise<WynikWczytania> {
  const lokalne = kluczeLokalne();
  try {
    const odp = await fetch('/api/pamiec');
    if (!odp.ok) throw new Error(String(odp.status));
    pamiec = (await odp.json()) as Record<string, string>;
    serwerDostepny = true;
  } catch {
    pamiec = { ...lokalne };
    return wynikWczytania;
  }
  const parametry = new URLSearchParams(window.location.search);
  const wymuszone = parametry.has('przenies');
  const pustaNaSerwerze = Object.keys(pamiec).length === 0;
  const zmiany: Record<string, string> = {};
  for (const [k, v] of Object.entries(lokalne)) {
    if (wymuszone || !(k in pamiec)) zmiany[k] = v;
  }
  Object.assign(pamiec, zmiany);
  await wyslij(zmiany);
  if (wymuszone) {
    parametry.delete('przenies');
    window.history.replaceState(null, '', window.location.pathname + (parametry.size ? `?${parametry}` : ''));
  }
  window.addEventListener('pagehide', () => wyslijOczekujace(true));
  wynikWczytania = { przeniesiono: Object.keys(zmiany).length, wymuszone, pustaNaSerwerze };
  return wynikWczytania;
}

export function czytaj(klucz: string): string | null {
  return klucz in pamiec ? pamiec[klucz] : null;
}

export function zapisz(klucz: string, wartosc: string | null) {
  if (wartosc === null) delete pamiec[klucz];
  else pamiec[klucz] = wartosc;
  try {
    if (wartosc === null) window.localStorage.removeItem(klucz);
    else window.localStorage.setItem(klucz, wartosc);
  } catch {
    /* localStorage zablokowany - wystarczy serwer */
  }
  oczekujace[klucz] = wartosc;
  clearTimeout(licznik);
  licznik = setTimeout(() => wyslijOczekujace(), 400);
}
