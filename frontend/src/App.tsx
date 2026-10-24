import {
  Alert,
  AppShell,
  Badge,
  Box,
  Button,
  Center,
  Group,
  Loader,
  Progress,
  Select,
  Stack,
  Tabs,
  Text,
  Title,
  Tooltip,
} from '@mantine/core';
import { useDebouncedValue } from '@mantine/hooks';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react';

import { api, type Filtry, type Stan, type Wiersz, type ZapytanieRankingu } from './api';
import ListaZyczen from './komponenty/ListaZyczen';
import { kluczZawodnika, usePamiec, type WpisListy } from './pamiec';

import Ligi from './komponenty/Ligi';
import MojaTaktyka from './komponenty/MojaTaktyka';
import MojaKadra from './komponenty/MojaKadra';
import Okazje from './komponenty/Okazje';
import PanelBoczny, { PUSTE_FILTRY, type Ustawienia } from './komponenty/PanelBoczny';
import PanelZrodla from './komponenty/PanelZrodla';

import TabelaRankingu from './komponenty/TabelaRankingu';
// Komponenty z wykresami (ECharts) ladowane dopiero przy pierwszym uzyciu
const KartaZawodnika = lazy(() => import('./komponenty/KartaZawodnika'));
const Porownanie = lazy(() => import('./komponenty/Porownanie'));
const Wykresy = lazy(() => import('./komponenty/Wykresy'));

const POZYCJE = ['Bramkarz', 'Środkowy Obrońca', 'Boczny Obrońca', 'Wahadłowy', 'Defensywny Pomocnik', 'Środkowy Pomocnik',
  'Ofensywny Pomocnik', 'Skrzydłowy', 'Napastnik'];

// Zdarzenia serwera (SSE): nowa wersja danych albo zmiana statusu wczytywania -> odswiezenie stanu
function useZdarzeniaSerwera() {
  const klient = useQueryClient();
  useEffect(() => {
    const zrodlo = new EventSource('/api/zdarzenia');
    zrodlo.onmessage = () => klient.invalidateQueries({ queryKey: ['stan'] });
    return () => zrodlo.close();
  }, [klient]);
}

// Etap odczytu zapisu i czas od startu (odswiezany co sekunde)
function PostepWczytywania({ stan, szeroki }: { stan: Stan; szeroki?: boolean }) {
  const [teraz, setTeraz] = useState(() => Date.now() / 1000);
  useEffect(() => {
    const t = setInterval(() => setTeraz(Date.now() / 1000), 1000);
    return () => clearInterval(t);
  }, []);
  const etap = stan.etap;
  const sekundy = etap ? Math.max(0, Math.round(teraz - etap.start)) : 0;
  if (!szeroki) {
    return (
      <Group gap={6} wrap="nowrap">
        <Loader size="xs" />
        <Text size="sm" c="dimmed">{etap ? `${etap.nazwa} (${etap.nr + 1}/${etap.z}) · ${sekundy} s` : stan.komunikat}</Text>
      </Group>
    );
  }
  return (
    <Stack w={420} gap={6}>
      <Text>{stan.komunikat}</Text>
      {etap && <Progress value={((etap.nr + 0.5) / etap.z) * 100} animated />}
      {etap && <Text size="sm" c="dimmed">Etap {etap.nr + 1} z {etap.z} · {sekundy} s</Text>}
      <Text size="xs" c="dimmed">Kolejne otwarcie tego samego zapisu będzie natychmiastowe.</Text>
    </Stack>
  );
}

export default function App() {
  useZdarzeniaSerwera();
  const klient = useQueryClient();
  const [panelZrodla, setPanelZrodla] = useState(false);
  // Pozycja w zwyklym stanie zapamietywanym w localStorage (bez synchronizacji miedzy kartami
  // przegladarki) - zmienia sie tylko po kliknieciu uzytkownika
  const [pozycjaZapisana, setPozycja] = usePamiec('fm-pozycja', 'Napastnik');
  const pozycja = POZYCJE.includes(pozycjaZapisana) ? pozycjaZapisana : 'Napastnik';
  const [lista, setLista] = usePamiec<WpisListy[]>('fm-lista-zyczen', []);
  // Wybor w karcie "Okazje": wspolny dla wszystkich pozycji, zapamietany (domyslnie nic nie zaznaczone)
  const [okazjeWybrane, setOkazjeWybrane] = usePamiec<string[]>('fm-okazje-wybrane', []);
  const [okazjeBezMojego, setOkazjeBezMojego] = usePamiec('fm-okazje-bez-mojego', true);
  const ulubione = useMemo(() => new Set(lista.map((w) => w.klucz)), [lista]);
  const [ustawienia, setUstawienia] = usePamiec<Ustawienia>('fm-ustawienia',
    { k_baza: 5, ignoruj_mnoznik: false, pokaz_ukryte: false });
  const [wagiWlasne, setWagiWlasne] = usePamiec<Record<string, Record<string, number>>>('fm-wagi', {});
  const [filtryPozycji, setFiltryPozycji] = useState<Record<string, Filtry>>({});
  const [wybrani, setWybrani] = useState<Record<string, string[]>>({});
  const [karta, setKarta] = useState<string | null>(null);
  const [kartaWiersz, setKartaWiersz] = useState<Wiersz | undefined>(undefined);
  const [zakladka, setZakladka] = useState<string | null>('ranking');

  const stan = useQuery({ queryKey: ['stan'], queryFn: api.stan, staleTime: 0 });

  // Bez zrodla danych po starcie od razu pytamy, co wczytac
  const zapytano = useRef(false);
  useEffect(() => {
    if (!zapytano.current && stan.data) {
      zapytano.current = true;
      if (stan.data.status === 'pusto') setPanelZrodla(true);
    }
  }, [stan.data]);
  const wersja = stan.data?.wersja ?? 0;
  const gotowe = (stan.data?.pozycje[pozycja] ?? 0) > 0;

  const meta = useQuery({
    queryKey: ['meta', wersja, pozycja],
    queryFn: () => api.metaPozycji(pozycja),
    enabled: gotowe,
  });

  const filtry = filtryPozycji[pozycja] ?? PUSTE_FILTRY;
  const wagi = wagiWlasne[pozycja] ?? meta.data?.wagi_domyslne ?? {};
  const zapytanie: ZapytanieRankingu = useMemo(
    () => ({
      pozycja,
      wagi: wagiWlasne[pozycja] ?? null,
      ignoruj_mnoznik: ustawienia.ignoruj_mnoznik,
      k_baza: ustawienia.k_baza,
      pokaz_ukryte: ustawienia.pokaz_ukryte,
      filtry,
    }),
    [pozycja, wagiWlasne, ustawienia, filtry],
  );
  const [zapytanieOpoznione] = useDebouncedValue(zapytanie, 250);

  const ranking = useQuery({
    queryKey: ['ranking', wersja, zapytanieOpoznione],
    queryFn: () => api.ranking(zapytanieOpoznione),
    enabled: gotowe && zapytanieOpoznione.pozycja === pozycja,
    // poprzedni wynik zostaje na ekranie tylko przy zmianie filtrow tej samej pozycji
    placeholderData: (poprzedni) => (poprzedni?.pozycja === zapytanieOpoznione.pozycja ? poprzedni : undefined),
  });
  // Tabela nigdy nie pokazuje wierszy innej pozycji niz wybrana (np. gdy odpowiedz jeszcze nie doszla)
  const rankingPozycji = ranking.data?.pozycja === pozycja ? ranking.data : undefined;

  const wiersze = rankingPozycji?.wiersze ?? [];
  const wierszKarty = wiersze.find((w) => w['ID'] === karta) ?? (kartaWiersz?.['ID'] === karta ? kartaWiersz : undefined);
  const otworzKarte = (id: string, wiersz?: Wiersz) => {
    setKarta(id);
    setKartaWiersz(wiersz);
  };
  const wybraniPozycji = wybrani[pozycja] ?? [];
  const s = stan.data;
  const mojKlubUid = s?.meta.moj_klub_uid;
  const mojeKluby = s?.meta.moje_kluby ?? [];

  const szukajNastepcy = (poz: string) => {
    setPozycja(poz);
    setFiltryPozycji({ ...filtryPozycji, [poz]: { ...(filtryPozycji[poz] ?? PUSTE_FILTRY), bez_mojego_klubu: true } });
    setZakladka('ranking');
  };
  // Gwiazdka: dodaje zawodnika z pozycja, w ktorej jest teraz ogladany, albo usuwa go z listy
  const przelaczUlubione = (w: Wiersz, poz: string = pozycja) => {
    const klucz = kluczZawodnika(w);
    if (ulubione.has(klucz)) setLista(lista.filter((x) => x.klucz !== klucz));
    else {
      setLista([...lista, {
        klucz, pozycja: poz, pilkarz: String(w['Piłkarz'] ?? ''), klub: String(w['Klub'] ?? ''),
        dodano: new Date().toISOString(),
      }]);
    }
  };
  const zmienMojKlub = async (uid: string | null) => {
    if (!uid) return;
    klient.setQueryData(['stan'], await api.mojKlub(Number(uid)));
  };

  return (
    <AppShell header={{ height: 56 }} navbar={{ width: 320, breakpoint: 'sm' }} padding={0}>
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between" wrap="nowrap">
          <Group gap="sm" wrap="nowrap">
            <Title order={3}>FM26 Moneyball</Title>
            {s?.meta.nazwa_zapisu && <Badge variant="light" size="lg">{s.meta.nazwa_zapisu}</Badge>}
            {s?.meta.data_gry && <Badge variant="outline" color="gray">data w grze: {s.meta.data_gry}</Badge>}
            {mojeKluby.length > 1 ? (
              <Select size="xs" w={220} aria-label="Twój klub" allowDeselect={false}
                leftSection={<span className="legenda-moj-klub" />}
                value={mojKlubUid !== null && mojKlubUid !== undefined ? String(mojKlubUid) : null}
                data={mojeKluby.map((k) => ({ value: String(k.uid), label: k.nazwa }))} onChange={zmienMojKlub} />
            ) : s?.meta.moj_klub ? (
              <Tooltip label="Zawodnicy twojego klubu są wyróżnieni w tabelach na bursztynowo">
                <Badge variant="light" color="yellow" size="lg" leftSection={<span className="legenda-moj-klub" />}>
                  Twój klub: {s.meta.moj_klub}
                </Badge>
              </Tooltip>
            ) : null}
          </Group>
          <Group gap="sm" wrap="nowrap">
            {s?.status === 'wczytywanie' && <PostepWczytywania stan={s} />}
            {s?.zrodlo.typ === 'folder' && s.zrodlo.sledz && !s.zrodlo.plik && s.status === 'gotowe' && (
              <Tooltip label="Nowy zapis gry zostanie wczytany automatycznie">
                <Badge color="teal" variant="dot">śledzę zapisy gry</Badge>
              </Tooltip>
            )}
            <Button variant="light" onClick={() => setPanelZrodla(true)}>Źródło danych</Button>
          </Group>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="md">
        <PanelBoczny
          pozycje={POZYCJE}
          liczby={s?.pozycje ?? {}}
          pozycja={pozycja}
          setPozycja={setPozycja}
          meta={meta.data}
          filtry={filtry}
          setFiltry={(f) => setFiltryPozycji({ ...filtryPozycji, [pozycja]: f })}
          wagi={wagi}
          setWagi={(w) => {
            const kopia = { ...wagiWlasne };
            if (w) kopia[pozycja] = w;
            else delete kopia[pozycja];
            setWagiWlasne(kopia);
          }}
          ustawienia={ustawienia}
          setUstawienia={setUstawienia}
          maMojKlub={!!s?.meta.moj_klub_uid}
          pominiete={rankingPozycji?.pominiete ?? []}
        />
      </AppShell.Navbar>

      <AppShell.Main style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
        {s?.status === 'blad' && <Alert color="red" m="md" title="Problem z danymi">{s.komunikat}</Alert>}
        {(s?.meta.ostrzezenia ?? []).map((o) => <Alert key={o} color="yellow" mx="md" mt="xs">{o}</Alert>)}

        {!gotowe ? (
          <Center style={{ flex: 1 }}>
            <Stack align="center" maw={520}>
              {s?.status === 'wczytywanie' ? (
                <PostepWczytywania stan={s} szeroki />
              ) : (
                <>
                  <Title order={3}>Brak danych</Title>
                  <Text c="dimmed" ta="center">
                    Wybierz zapis z folderu gry (najszybciej; aplikacja może też śledzić kolejne zapisy), wgraj plik .fm albo
                    wypróbuj dane demo.
                  </Text>
                  <Button onClick={() => setPanelZrodla(true)}>Wybierz źródło danych</Button>
                </>
              )}
            </Stack>
          </Center>
        ) : (
          <Tabs value={zakladka} onChange={setZakladka} style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <Tabs.List px="md">
              <Tabs.Tab value="ranking">
                Ranking {rankingPozycji ? `(${rankingPozycji.liczba} z ${rankingPozycji.liczba_wszystkich}` : ''}
                {rankingPozycji?.liczba_kandydatow ? ` + ${rankingPozycji.liczba_kandydatow} kandydatów` : ''}
                {rankingPozycji ? ')' : ''}
              </Tabs.Tab>
              <Tabs.Tab value="okazje">Okazje</Tabs.Tab>
              <Tabs.Tab value="lista">Lista życzeń {lista.length ? `(${lista.length})` : ''}</Tabs.Tab>
              {mojKlubUid !== null && mojKlubUid !== undefined && <Tabs.Tab value="kadra">Moja kadra</Tabs.Tab>}
              {mojKlubUid !== null && mojKlubUid !== undefined && <Tabs.Tab value="taktyka">Moja taktyka</Tabs.Tab>}
              <Tabs.Tab value="porownanie">Porównanie {wybraniPozycji.length ? `(${wybraniPozycji.length})` : ''}</Tabs.Tab>
              <Tabs.Tab value="wykresy">Wykresy</Tabs.Tab>
              <Tabs.Tab value="ligi">Ligi i kraje</Tabs.Tab>
              {ranking.isFetching && <Loader size="xs" ml="sm" mt={10} />}
            </Tabs.List>

            <Tabs.Panel value="ranking" style={{ flex: 1, minHeight: 0 }}>
              <Box p="sm" h="100%" style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {ranking.error && <Alert color="red">{(ranking.error as Error).message}</Alert>}
                <Text size="xs" c="dimmed">
                  {s?.meta.moj_klub && (
                    <><span className="legenda-moj-klub" /> zawodnicy twojego klubu ({s.meta.moj_klub}) · </>
                  )}
                  {filtry.kandydaci && (
                    <><span className="legenda-kandydat" /> kandydaci do przekwalifikowania z innych pozycji · </>
                  )}
                  kliknij nazwisko, aby otworzyć kartę · zaznacz do 4 zawodników do porównania
                </Text>
                {!rankingPozycji && !ranking.error && (
                  <Center style={{ flex: 1 }}><Loader /></Center>
                )}
                {rankingPozycji && (
                  <Box style={{ flex: 1, minHeight: 0 }}>
                  <TabelaRankingu
                    key={pozycja}
                    kolumny={rankingPozycji.kolumny}
                    wiersze={wiersze}
                    mojKlubUid={mojKlubUid}
                    naWybor={otworzKarte}
                    naZaznaczenie={(ids) => setWybrani({ ...wybrani, [pozycja]: ids.slice(0, 4) })}
                    ulubione={ulubione}
                    przelaczUlubione={przelaczUlubione}
                  />
                  </Box>
                )}
              </Box>
            </Tabs.Panel>
            <Tabs.Panel value="okazje" style={{ flex: 1, minHeight: 0 }}>
              {zakladka === 'okazje' && meta.data && (
                <Okazje zapytanie={zapytanieOpoznione} okazje={meta.data.okazje} wersja={wersja} mojKlubUid={mojKlubUid}
                  naWybor={otworzKarte} ulubione={ulubione} przelaczUlubione={przelaczUlubione}
                  wybrane={okazjeWybrane} setWybrane={setOkazjeWybrane}
                  pominMoj={okazjeBezMojego} setPominMoj={setOkazjeBezMojego} />
              )}
            </Tabs.Panel>
            <Tabs.Panel value="lista" style={{ flex: 1, minHeight: 0 }}>
              {zakladka === 'lista' && (
                <ListaZyczen lista={lista} setLista={setLista} wersja={wersja} wagi={wagiWlasne} ustawienia={ustawienia}
                  mojKlubUid={mojKlubUid}
                  naWybor={(poz, id, wiersz) => {
                    setPozycja(poz);
                    otworzKarte(id, wiersz);
                  }} />
              )}
            </Tabs.Panel>
            <Tabs.Panel value="kadra" style={{ overflow: 'auto' }}>
              {zakladka === 'kadra' && (
                <MojaKadra wersja={wersja} wagi={wagiWlasne} ustawienia={ustawienia} szukajNastepcy={szukajNastepcy}
                  otworz={(poz, id, wiersz) => {
                    setPozycja(poz);
                    otworzKarte(id, wiersz);
                  }} />
              )}
            </Tabs.Panel>
            <Tabs.Panel value="taktyka" style={{ overflow: 'auto' }}>
              {zakladka === 'taktyka' && <MojaTaktyka wersja={wersja} />}
            </Tabs.Panel>
            <Tabs.Panel value="ligi" style={{ overflow: 'auto' }}>
              {zakladka === 'ligi' && <Ligi wersja={wersja} />}
            </Tabs.Panel>
            <Tabs.Panel value="porownanie" style={{ overflow: 'auto' }}>
              {zakladka === 'porownanie' && (
                <Suspense fallback={<Loader m="md" />}>
                  <Porownanie pozycja={pozycja} wersja={wersja} wiersze={wiersze} wybrani={wybraniPozycji}
                    setWybrani={(ids) => setWybrani({ ...wybrani, [pozycja]: ids })} kandydaci={filtry.kandydaci} />
                </Suspense>
              )}
            </Tabs.Panel>
            <Tabs.Panel value="wykresy" style={{ overflow: 'auto' }}>
              {zakladka === 'wykresy' && rankingPozycji && (
                <Suspense fallback={<Loader m="md" />}>
                  <Wykresy wiersze={wiersze} kolumny={rankingPozycji.kolumny} modelWyceny={rankingPozycji.model_wyceny}
                    mojKlubUid={mojKlubUid} naWybor={setKarta} />
                </Suspense>
              )}
            </Tabs.Panel>
          </Tabs>
        )}
      </AppShell.Main>

      <PanelZrodla otwarty={panelZrodla} zamknij={() => setPanelZrodla(false)} stan={s} />
      {karta && (
      <Suspense fallback={null}>
      <KartaZawodnika
        id={karta}
        wiersz={wierszKarty}
        zapytanie={zapytanie}
        wersja={wersja}
        mojKlubUid={mojKlubUid}
        ulubiona={!!wierszKarty && ulubione.has(kluczZawodnika(wierszKarty))}
        przelaczUlubiona={() => wierszKarty && przelaczUlubione(wierszKarty)}
        zamknij={() => setKarta(null)}
        otworz={setKarta}
        dodajDoPorownania={(id) => {
          const nowi = wybraniPozycji.includes(id) ? wybraniPozycji : [...wybraniPozycji, id].slice(-4);
          setWybrani({ ...wybrani, [pozycja]: nowi });
        }}
      />
      </Suspense>
      )}
    </AppShell>
  );
}
