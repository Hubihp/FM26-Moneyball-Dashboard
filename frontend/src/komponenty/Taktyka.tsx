import { Alert, Badge, Button, Card, Group, Loader, Menu, ScrollArea, Select, Stack, Text, TextInput, Title } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';
import { useEffect, useMemo, useRef, useState } from 'react';

import { api, type ZawodnikSkladu } from '../api';
import { formatuj, kolorWyniku } from '../format';
import { usePamiec } from '../pamiec';
import {
  FORMACJE, SKROTY, najlepszaXI, naturalny, przypisz, slotyFormacji, wynikNa, zamienSloty, zmienFormacje,
  type Slot, type Ustawienie,
} from '../taktyka';
import type { Ustawienia } from './PanelBoczny';

type Props = {
  wersja: number;
  wagi: Record<string, Record<string, number>>;
  ustawienia: Ustawienia;
  tylkoPierwsza: boolean;
  otworz: (pozycja: string, id: string) => void;
};

const POZYCJE = Object.keys(SKROTY);
const PROG_PRZECIAGANIA = 4;      // px - mniejszy ruch to klikniecie
const MALO_MINUT = 1000;

type Przeciaganie = { typ: 'slot' | 'gracz'; id: string; sx: number; sy: number; x: number; y: number; aktywne: boolean };
const nazwisko = (z: ZawodnikSkladu) => z.Piłkarz.split(' ').slice(-1)[0];
const najlepszyWynik = (z: ZawodnikSkladu) => Math.max(...Object.values(z.score), -Infinity);

// Pionowe boisko (68 x 105 m): moja bramka na dole, atak w gore
function Murawa() {
  const linia = { fill: 'none', stroke: 'rgba(255,255,255,0.85)', strokeWidth: 0.35 };
  const pole = (y: number, dol: boolean) => {
    const k = dol ? -1 : 1;
    return (
      <g>
        <rect x={13.84} y={dol ? y - 16.5 : y} width={40.32} height={16.5} {...linia} />
        <rect x={24.84} y={dol ? y - 5.5 : y} width={18.32} height={5.5} {...linia} />
        <circle cx={34} cy={y + k * 11} r={0.35} fill="white" />
        <path d={`M ${34 - 7.3} ${y + k * 16.5} A 9.15 9.15 0 0 ${dol ? 1 : 0} ${34 + 7.3} ${y + k * 16.5}`} {...linia} />
        <rect x={30.34} y={dol ? y : y - 2} width={7.32} height={2} fill="rgba(255,255,255,0.25)" stroke="white" strokeWidth={0.3} />
      </g>
    );
  };
  return (
    <svg viewBox="-3 -3 74 111" preserveAspectRatio="none" style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }}>
      <defs>
        <linearGradient id="murawa" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#2f9e5f" /><stop offset="1" stopColor="#1f7a47" />
        </linearGradient>
      </defs>
      <rect x={-3} y={-3} width={74} height={111} fill="url(#murawa)" />
      {Array.from({ length: 10 }, (_, i) => (
        <rect key={i} x={0} y={i * 10.5} width={68} height={10.5} fill={i % 2 ? 'rgba(255,255,255,0.035)' : 'rgba(0,0,0,0.04)'} />
      ))}
      <rect x={0} y={0} width={68} height={105} {...linia} />
      <line x1={0} y1={52.5} x2={68} y2={52.5} {...linia} />
      <circle cx={34} cy={52.5} r={9.15} {...linia} />
      <circle cx={34} cy={52.5} r={0.4} fill="white" />
      {pole(0, false)}
      {pole(105, true)}
    </svg>
  );
}

function Zeton({ slot, gracz, numer, wybrany, naKlik, naChwyt, przeciagany, naZmianePozycji, naZdjecie, naKarte }: {
  slot: Slot; gracz: ZawodnikSkladu | undefined; numer: number; wybrany: boolean; naKlik: () => void;
  naChwyt: (e: React.PointerEvent) => void; przeciagany: { x: number; y: number } | null;
  naZmianePozycji: (p: string) => void; naZdjecie: () => void; naKarte: () => void;
}) {
  const wynik = wynikNa(gracz, slot.pozycja);
  const poza = gracz && !naturalny(gracz, slot.pozycja);
  return (
    <div
      data-slot={slot.id}
      onPointerDown={naChwyt}
      onClick={naKlik}
      // przeciagany zeton sam podaza za kursorem (bez polprzezroczystej kopii) i nie zaslania celu upuszczenia
      style={{ position: 'absolute', left: `${przeciagany?.x ?? slot.x}%`, top: `${przeciagany?.y ?? slot.y}%`,
        transform: 'translate(-50%, -50%)', display: 'flex', flexDirection: 'column', alignItems: 'center',
        cursor: przeciagany ? 'grabbing' : 'grab', width: 110, zIndex: przeciagany ? 10 : wybrany ? 3 : 2,
        pointerEvents: przeciagany ? 'none' : undefined, touchAction: 'none', userSelect: 'none' }}
    >
      <Menu position="right" withinPortal shadow="md">
        <Menu.Target>
          <div onClick={(e) => e.stopPropagation()} title="Kliknij, aby zmienić pozycję"
            style={{ width: 42, height: 42, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: 'radial-gradient(circle at 35% 30%, #ff6b6b, #c92a2a)', color: 'white', fontWeight: 800,
              fontSize: SKROTY[slot.pozycja].length > 2 ? 11 : 14, boxShadow: '0 3px 6px rgba(0,0,0,0.45)',
              border: `2px solid ${wybrany ? '#ffd43b' : poza ? '#fd7e14' : 'white'}` }}>
            {SKROTY[slot.pozycja] ?? numer}
          </div>
        </Menu.Target>
        <Menu.Dropdown>
          <Menu.Label>Pozycja na tym miejscu</Menu.Label>
          {POZYCJE.map((p) => (
            <Menu.Item key={p} onClick={() => naZmianePozycji(p)} fw={p === slot.pozycja ? 700 : undefined}>
              {SKROTY[p]} · {p}
            </Menu.Item>
          ))}
        </Menu.Dropdown>
      </Menu>
      {gracz ? (
        <div style={{ marginTop: 3, background: 'rgba(15,17,20,0.82)', borderRadius: 6, padding: '1px 6px', textAlign: 'center',
          maxWidth: 110 }}>
          <Text size="xs" fw={700} c="white" truncate onDoubleClick={naKarte} title={`${gracz.Piłkarz} - dwuklik: karta`}>
            {nazwisko(gracz)}
            <span onClick={(e) => { e.stopPropagation(); naZdjecie(); }} title="Zdejmij z boiska"
              style={{ marginLeft: 4, color: '#adb5bd', cursor: 'pointer' }}>×</span>
          </Text>
          {wynik !== null ? (
            <Text size="xs" fw={700} style={{ color: kolorWyniku(wynik) }}>{formatuj(wynik, 'score')}</Text>
          ) : (
            <Text size="xs" c="orange">poza pozycją · {gracz.oceny[slot.pozycja] ?? '?'}/20</Text>
          )}
        </div>
      ) : (
        <Text size="xs" mt={3} c="white" style={{ background: 'rgba(0,0,0,0.35)', borderRadius: 6, padding: '0 6px' }}>
          przeciągnij zawodnika
        </Text>
      )}
    </div>
  );
}

// Interaktywna tablica taktyczna: formacja, zawodnicy przeciagani na pozycje, zapisane ustawienia
export default function Taktyka({ wersja, wagi, ustawienia, tylkoPierwsza, otworz }: Props) {
  const sklad = useQuery({
    queryKey: ['sklad', wersja, wagi, ustawienia.k_baza, ustawienia.ignoruj_mnoznik, tylkoPierwsza],
    queryFn: () => api.sklad({ wagi, ignoruj_mnoznik: ustawienia.ignoruj_mnoznik, k_baza: ustawienia.k_baza,
      tylko_pierwsza: tylkoPierwsza }),
  });
  const [biezace, setBiezace] = usePamiec<Ustawienie | null>('fm-taktyka', null);
  const [zapisane, setZapisane] = usePamiec<Record<string, Ustawienie>>('fm-taktyki', {});
  const [nazwa, setNazwa] = usePamiec('fm-taktyka-nazwa', '');
  const [wybranySlot, setWybranySlot] = useState<string | null>(null);
  const [filtr, setFiltr] = useState<string | null>(null);
  const boisko = useRef<HTMLDivElement>(null);
  const [przeciaganie, setPrzeciaganie] = useState<Przeciaganie | null>(null);
  const przeciaganieRef = useRef<Przeciaganie | null>(null);
  const poPrzeciagnieciu = useRef(false);     // klikniecie po upuszczeniu jest ignorowane
  const upuscRef = useRef<(p: Przeciaganie) => void>(() => undefined);
  const aktywne = przeciaganie !== null;

  // przeciaganie na zdarzeniach wskaznika (dziala w WebView2), nasluch na oknie do konca ruchu
  useEffect(() => {
    if (!aktywne) return;
    const ruch = (e: PointerEvent) => {
      const p = przeciaganieRef.current;
      if (!p) return;
      const nowe = { ...p, x: e.clientX, y: e.clientY,
        aktywne: p.aktywne || Math.hypot(e.clientX - p.sx, e.clientY - p.sy) > PROG_PRZECIAGANIA };
      przeciaganieRef.current = nowe;
      setPrzeciaganie(nowe);
    };
    const koniec = () => {
      const p = przeciaganieRef.current;
      przeciaganieRef.current = null;
      setPrzeciaganie(null);
      if (p?.aktywne) {
        poPrzeciagnieciu.current = true;
        setTimeout(() => { poPrzeciagnieciu.current = false; }, 0);
        upuscRef.current(p);
      }
    };
    const zaznaczanie = document.body.style.userSelect;
    document.body.style.userSelect = 'none';
    window.addEventListener('pointermove', ruch);
    window.addEventListener('pointerup', koniec);
    window.addEventListener('pointercancel', koniec);
    return () => {
      document.body.style.userSelect = zaznaczanie;
      window.removeEventListener('pointermove', ruch);
      window.removeEventListener('pointerup', koniec);
      window.removeEventListener('pointercancel', koniec);
    };
  }, [aktywne]);
  const chwyc = (e: React.PointerEvent, typ: 'slot' | 'gracz', id: string) => {
    if (e.button !== 0) return;
    if (e.pointerType === 'mouse') e.preventDefault();      // bez zaznaczania tekstu podczas przeciagania
    const p = { typ, id, sx: e.clientX, sy: e.clientY, x: e.clientX, y: e.clientY, aktywne: false };
    przeciaganieRef.current = p;
    setPrzeciaganie(p);
  };
  const zawodnicy = useMemo(() => sklad.data?.zawodnicy ?? [], [sklad.data]);
  const wgKlucza = useMemo(() => Object.fromEntries(zawodnicy.map((z) => [z.klucz, z])), [zawodnicy]);

  // domyslnie (bez zapisanego ustawienia): 4-3-3 z najlepsza XI
  useEffect(() => {
    if (!biezace && zawodnicy.length) {
      const sloty = slotyFormacji('4-3-3');
      setBiezace({ formacja: '4-3-3', sloty, przypisania: najlepszaXI(sloty, zawodnicy) });
    }
  }, [biezace, zawodnicy, setBiezace]);

  if (sklad.isLoading) return <Loader m="md" />;
  if (sklad.error) return <Alert color="red">{(sklad.error as Error).message}</Alert>;
  if (!biezace) return zawodnicy.length ? <Loader m="md" /> : <Alert color="gray">Brak zawodników w kadrze.</Alert>;

  const u = biezace;
  const naBoisku = new Set(Object.values(u.przypisania));
  const wSkladzie = u.sloty.map((s) => ({ s, z: wgKlucza[u.przypisania[s.id]] })).filter((x) => x.z);
  const wyniki = wSkladzie.map(({ s, z }) => wynikNa(z, s.pozycja)).filter((w): w is number => w !== null);
  const sredniWiek = wSkladzie.reduce((a, { z }) => a + (z!.Wiek ?? 0), 0) / Math.max(wSkladzie.length, 1);
  const pozaPozycja = wSkladzie.filter(({ s, z }) => !naturalny(z, s.pozycja)).length;
  const lista = zawodnicy
    .filter((z) => !filtr || wynikNa(z, filtr) !== null)
    .sort((a, b) => (filtr ? (wynikNa(b, filtr) ?? 0) - (wynikNa(a, filtr) ?? 0) : najlepszyWynik(b) - najlepszyWynik(a)));

  // punkt ekranu -> % boiska (obciete do murawy)
  const naBoiskuProcent = (x: number, y: number) => {
    const r = boisko.current?.getBoundingClientRect();
    if (!r) return null;
    return { x: Math.min(97, Math.max(3, ((x - r.left) / r.width) * 100)),
      y: Math.min(97, Math.max(3, ((y - r.top) / r.height) * 100)) };
  };
  // Upuszczenie: cel spod kursora (przeciagany element ma pointer-events: none, wiec go nie zaslania)
  upuscRef.current = (p: Przeciaganie) => {
    const elementy = document.elementsFromPoint(p.x, p.y);
    const celSlot = elementy.map((el) => el.closest('[data-slot]')).find((el) => el && el.getAttribute('data-slot') !== p.id);
    const slotCel = celSlot?.getAttribute('data-slot') ?? null;
    const naBoisku = elementy.some((el) => el.closest('[data-boisko]'));
    const naLiscie = elementy.some((el) => el.closest('[data-lista]'));
    const punkt = naBoiskuProcent(p.x, p.y);
    if (p.typ === 'gracz') {
      if (slotCel) setBiezace(przypisz(u, slotCel, p.id));
      else if (naBoisku && punkt) {
        // dowolne miejsce boiska: najblizsza pozycja
        const najblizszy = [...u.sloty].sort((a, b) =>
          Math.hypot(a.x - punkt.x, (a.y - punkt.y) * 1.5) - Math.hypot(b.x - punkt.x, (b.y - punkt.y) * 1.5))[0];
        if (najblizszy) setBiezace(przypisz(u, najblizszy.id, p.id));
      }
    } else if (slotCel) setBiezace(zamienSloty(u, p.id, slotCel));
    else if (naBoisku && punkt) setBiezace({ ...u, sloty: u.sloty.map((s) => (s.id === p.id ? { ...s, ...punkt } : s)) });
    else if (naLiscie) zdejmij(p.id);
  };
  const zdejmij = (slotId: string) => {
    const przypisania = { ...u.przypisania };
    delete przypisania[slotId];
    setBiezace({ ...u, przypisania });
  };
  const kliknijGracza = (z: ZawodnikSkladu) => {
    if (wybranySlot) {
      setBiezace(przypisz(u, wybranySlot, z.klucz));
      setWybranySlot(null);
    }
  };
  const zapisz = (jako: string) => {
    if (!jako.trim()) return;
    setZapisane({ ...zapisane, [jako.trim()]: u });
    setNazwa(jako.trim());
  };

  return (
    <Group align="flex-start" gap="md" wrap="nowrap">
      {przeciaganie?.aktywne && przeciaganie.typ === 'gracz' && wgKlucza[przeciaganie.id] && (
        <div style={{ position: 'fixed', left: przeciaganie.x, top: przeciaganie.y, transform: 'translate(-50%, -50%)',
          pointerEvents: 'none', zIndex: 1000, background: '#c92a2a', color: 'white', fontWeight: 700, fontSize: 13,
          padding: '4px 10px', borderRadius: 14, boxShadow: '0 4px 10px rgba(0,0,0,0.5)', whiteSpace: 'nowrap' }}>
          {wgKlucza[przeciaganie.id].Piłkarz}
        </div>
      )}
      <div ref={boisko} data-boisko
        style={{ position: 'relative', height: 'min(78vh, 900px)', aspectRatio: '74 / 111', flexShrink: 0,
          borderRadius: 10, overflow: 'hidden', boxShadow: '0 4px 18px rgba(0,0,0,0.45)' }}>
        <Murawa />
        {u.sloty.map((s, i) => (
          <Zeton key={s.id} slot={s} numer={i + 1} gracz={wgKlucza[u.przypisania[s.id]]} wybrany={wybranySlot === s.id}
            naKlik={() => !poPrzeciagnieciu.current && setWybranySlot(wybranySlot === s.id ? null : s.id)}
            naChwyt={(e) => chwyc(e, 'slot', s.id)}
            przeciagany={przeciaganie?.aktywne && przeciaganie.typ === 'slot' && przeciaganie.id === s.id
              ? naBoiskuProcent(przeciaganie.x, przeciaganie.y) : null}
            naZdjecie={() => zdejmij(s.id)}
            naZmianePozycji={(p) => setBiezace({ ...u, sloty: u.sloty.map((x) => (x.id === s.id ? { ...x, pozycja: p } : x)) })}
            naKarte={() => {
              const z = wgKlucza[u.przypisania[s.id]];
              const id = z && (z.id_w_pulach[s.pozycja] ?? Object.values(z.id_w_pulach)[0]);
              const poz = z && (z.id_w_pulach[s.pozycja] ? s.pozycja : Object.keys(z.id_w_pulach)[0]);
              if (id && poz) otworz(poz, id);
            }} />
        ))}
      </div>

      <Stack gap="sm" style={{ flex: 1, minWidth: 280 }}>
        <Group gap="xs" align="end">
          <Select label="Formacja" w={130} data={FORMACJE} value={u.formacja} allowDeselect={false}
            onChange={(f) => f && setBiezace(zmienFormacje(u, f))} />
          <Button variant="light" onClick={() => setBiezace({ ...u, przypisania: najlepszaXI(u.sloty, zawodnicy) })}>
            Ułóż najlepszą XI
          </Button>
          <Button variant="default" onClick={() => setBiezace({ ...u, przypisania: {} })}>Wyczyść</Button>
          <Button variant="subtle" color="gray" onClick={() => setBiezace({ ...u, sloty: slotyFormacji(u.formacja).map((s, i) => ({ ...s, pozycja: u.sloty[i]?.pozycja ?? s.pozycja })) })}>
            Wyrównaj pozycje
          </Button>
        </Group>
        <Group gap="xs" align="end">
          <Select label="Zapisane ustawienia" w={200} placeholder="brak" clearable data={Object.keys(zapisane)}
            value={zapisane[nazwa] ? nazwa : null}
            onChange={(n) => {
              if (n && zapisane[n]) {
                setBiezace(zapisane[n]);
                setNazwa(n);
              } else setNazwa('');
            }} />
          <TextInput label="Nazwa" w={160} value={nazwa} onChange={(e) => setNazwa(e.currentTarget.value)} placeholder="np. Liga" />
          <Button onClick={() => zapisz(nazwa)} disabled={!nazwa.trim()}>Zapisz</Button>
          {zapisane[nazwa] && (
            <Button variant="subtle" color="red" onClick={() => {
              const kopia = { ...zapisane };
              delete kopia[nazwa];
              setZapisane(kopia);
              setNazwa('');
            }}>Usuń</Button>
          )}
        </Group>
        <Card withBorder padding="xs">
          <Group gap="lg">
            <Text size="sm">Średni SCORE XI: <b>{wyniki.length ? formatuj(wyniki.reduce((a, b) => a + b, 0) / wyniki.length, 'dec1') : '–'}</b></Text>
            <Text size="sm">Średni wiek: <b>{wSkladzie.length ? formatuj(sredniWiek, 'dec1') : '–'}</b></Text>
            <Text size="sm" c={pozaPozycja ? 'orange' : undefined}>Poza naturalną pozycją: <b>{pozaPozycja}</b></Text>
            <Text size="sm">Na boisku: <b>{wSkladzie.length}/11</b></Text>
          </Group>
        </Card>
        <Text size="xs" c="dimmed">
          Przeciągnij zawodnika z listy na pozycję (albo kliknij pozycję, a potem zawodnika). Żeton na żeton zamienia
          zawodników, żeton na wolne miejsce przesuwa pozycję. Kółko pozycji: zmiana pozycji; dwuklik na nazwisku: karta;
          × zdejmuje z boiska. SCORE liczony na pozycji na boisku; „poza pozycją” = ocena pozycji z gry (1–20).
        </Text>
        <Card withBorder padding="xs" data-lista>
          <Group justify="space-between" mb={6}>
            <Title order={6}>Kadra ({zawodnicy.length})</Title>
            <Select size="xs" w={190} placeholder="Wszystkie pozycje" clearable value={filtr} onChange={setFiltr}
              data={POZYCJE.map((p) => ({ value: p, label: `${SKROTY[p]} · ${p}` }))} />
          </Group>
          <ScrollArea h="min(46vh, 520px)">
            <Stack gap={4}>
              {lista.map((z) => {
                const wynik = filtr ? wynikNa(z, filtr) : najlepszyWynik(z);
                const pozycjeGracza = Object.keys(z.score).map((p) => SKROTY[p]).join(', ');
                return (
                  <Group key={z.klucz} data-gracz={z.klucz} gap="xs" wrap="nowrap" justify="space-between"
                    onPointerDown={(e) => chwyc(e, 'gracz', z.klucz)}
                    onClick={() => !poPrzeciagnieciu.current && kliknijGracza(z)}
                    style={{ padding: '4px 8px', borderRadius: 6, cursor: 'grab', opacity: naBoisku.has(z.klucz) ? 0.5 : 1,
                      background: 'var(--mantine-color-dark-6)', touchAction: 'none', userSelect: 'none' }}>
                    <div style={{ minWidth: 0 }}>
                      <Text size="sm" fw={600} truncate>{z.Piłkarz}</Text>
                      <Text size="xs" c="dimmed" truncate>
                        {pozycjeGracza || z.Pozycja} · {z.Wiek ?? '?'} lat ·{' '}
                        <span style={{ color: (z.Minuty ?? 0) < MALO_MINUT ? 'var(--mantine-color-orange-5)' : undefined }}
                          title={(z.Minuty ?? 0) < MALO_MINUT ? `Mniej niż ${MALO_MINUT} minut - mała próba, SCORE mniej pewny` : undefined}>
                          {formatuj(z.Minuty ?? 0, 'int')} min
                        </span>
                        {naBoisku.has(z.klucz) ? ' · na boisku' : ''}
                      </Text>
                    </div>
                    <Group gap={4} wrap="nowrap">
                      {z.Drużyna && z.Drużyna !== 'Pierwsza drużyna' && <Badge size="xs" color="gray">rez.</Badge>}
                      <Badge variant="filled" w={44} style={{ background: Number.isFinite(wynik) && wynik !== null ? kolorWyniku(wynik) : '#495057', color: '#111' }}>
                        {Number.isFinite(wynik) && wynik !== null ? formatuj(wynik, 'score') : '–'}
                      </Badge>
                    </Group>
                  </Group>
                );
              })}
            </Stack>
          </ScrollArea>
        </Card>
      </Stack>
    </Group>
  );
}
