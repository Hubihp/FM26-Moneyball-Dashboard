import { Alert, AppShell, Badge, Box, Button, Center, Group, Loader, Stack, Tabs, Text, Title, Tooltip } from '@mantine/core';
import { useDebouncedValue, useLocalStorage } from '@mantine/hooks';
import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useMemo, useState } from 'react';

import { api, type Filtry, type ZapytanieRankingu } from './api';
import KartaZawodnika from './komponenty/KartaZawodnika';
import PanelBoczny, { PUSTE_FILTRY, type Ustawienia } from './komponenty/PanelBoczny';
import PanelZrodla from './komponenty/PanelZrodla';
import Porownanie from './komponenty/Porownanie';
import TabelaRankingu from './komponenty/TabelaRankingu';
import Wykresy from './komponenty/Wykresy';

const POZYCJE = ['Bramkarz', 'Środkowy Obrońca', 'Boczny Obrońca', 'Defensywny Pomocnik', 'Środkowy Pomocnik', 'Skrzydłowy', 'Napastnik'];

// Zdarzenia serwera (SSE): nowa wersja danych albo zmiana statusu wczytywania -> odswiezenie stanu
function useZdarzeniaSerwera() {
  const klient = useQueryClient();
  useEffect(() => {
    const zrodlo = new EventSource('/api/zdarzenia');
    zrodlo.onmessage = () => klient.invalidateQueries({ queryKey: ['stan'] });
    return () => zrodlo.close();
  }, [klient]);
}

export default function App() {
  useZdarzeniaSerwera();
  const [panelZrodla, setPanelZrodla] = useState(false);
  const [pozycja, setPozycja] = useLocalStorage({ key: 'fm-pozycja', defaultValue: 'Napastnik' });
  const [ustawienia, setUstawienia] = useLocalStorage<Ustawienia>({
    key: 'fm-ustawienia', defaultValue: { k_baza: 5, ignoruj_mnoznik: false, pokaz_ukryte: false },
  });
  const [wagiWlasne, setWagiWlasne] = useLocalStorage<Record<string, Record<string, number>>>({ key: 'fm-wagi', defaultValue: {} });
  const [filtryPozycji, setFiltryPozycji] = useState<Record<string, Filtry>>({});
  const [wybrani, setWybrani] = useState<Record<string, string[]>>({});
  const [karta, setKarta] = useState<string | null>(null);
  const [zakladka, setZakladka] = useState<string | null>('ranking');

  const stan = useQuery({ queryKey: ['stan'], queryFn: api.stan, staleTime: 0 });
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
    placeholderData: keepPreviousData,
  });

  const wiersze = ranking.data?.wiersze ?? [];
  const wierszKarty = wiersze.find((w) => w['ID'] === karta);
  const wybraniPozycji = wybrani[pozycja] ?? [];
  const s = stan.data;

  return (
    <AppShell header={{ height: 56 }} navbar={{ width: 320, breakpoint: 'sm' }} padding={0}>
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between" wrap="nowrap">
          <Group gap="sm" wrap="nowrap">
            <Title order={3}>FM26 Moneyball</Title>
            {s?.meta.nazwa_zapisu && <Badge variant="light" size="lg">{s.meta.nazwa_zapisu}</Badge>}
            {s?.meta.data_gry && <Badge variant="outline" color="gray">data w grze: {s.meta.data_gry}</Badge>}
            {s?.meta.moj_klub && <Badge variant="outline" color="teal">{s.meta.moj_klub}</Badge>}
          </Group>
          <Group gap="sm" wrap="nowrap">
            {s?.status === 'wczytywanie' && (
              <Group gap={6}><Loader size="xs" /><Text size="sm" c="dimmed">{s.komunikat}</Text></Group>
            )}
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
          pominiete={ranking.data?.pominiete ?? []}
        />
      </AppShell.Navbar>

      <AppShell.Main style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
        {s?.status === 'blad' && <Alert color="red" m="md" title="Problem z danymi">{s.komunikat}</Alert>}
        {(s?.meta.ostrzezenia ?? []).map((o) => <Alert key={o} color="yellow" mx="md" mt="xs">{o}</Alert>)}

        {!gotowe ? (
          <Center style={{ flex: 1 }}>
            <Stack align="center" maw={520}>
              {s?.status === 'wczytywanie' ? (
                <><Loader /><Text>{s.komunikat}</Text></>
              ) : (
                <>
                  <Title order={3}>Brak danych</Title>
                  <Text c="dimmed" ta="center">
                    Wskaż folder zapisów FM26 (aplikacja sama wczyta najnowszy zapis i będzie śledzić kolejne), wgraj plik
                    .fm albo wypróbuj dane demo.
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
                Ranking {ranking.data ? `(${ranking.data.liczba} z ${ranking.data.liczba_wszystkich})` : ''}
              </Tabs.Tab>
              <Tabs.Tab value="porownanie">Porównanie {wybraniPozycji.length ? `(${wybraniPozycji.length})` : ''}</Tabs.Tab>
              <Tabs.Tab value="wykresy">Wykresy</Tabs.Tab>
              {ranking.isFetching && <Loader size="xs" ml="sm" mt={10} />}
            </Tabs.List>

            <Tabs.Panel value="ranking" style={{ flex: 1, minHeight: 0 }}>
              <Box p="sm" h="100%">
                {ranking.error && <Alert color="red">{(ranking.error as Error).message}</Alert>}
                {ranking.data && (
                  <TabelaRankingu
                    kolumny={ranking.data.kolumny}
                    wiersze={wiersze}
                    mojKlubUid={s?.meta.moj_klub_uid}
                    naWybor={setKarta}
                    naZaznaczenie={(ids) => setWybrani({ ...wybrani, [pozycja]: ids.slice(0, 4) })}
                  />
                )}
              </Box>
            </Tabs.Panel>
            <Tabs.Panel value="porownanie" style={{ overflow: 'auto' }}>
              <Porownanie pozycja={pozycja} wersja={wersja} wiersze={wiersze} wybrani={wybraniPozycji}
                setWybrani={(ids) => setWybrani({ ...wybrani, [pozycja]: ids })} />
            </Tabs.Panel>
            <Tabs.Panel value="wykresy" style={{ overflow: 'auto' }}>
              {ranking.data && <Wykresy wiersze={wiersze} kolumny={ranking.data.kolumny} naWybor={setKarta} />}
            </Tabs.Panel>
          </Tabs>
        )}
      </AppShell.Main>

      <PanelZrodla otwarty={panelZrodla} zamknij={() => setPanelZrodla(false)} stan={s} />
      <KartaZawodnika
        id={karta}
        wiersz={wierszKarty}
        zapytanie={zapytanie}
        wersja={wersja}
        zamknij={() => setKarta(null)}
        otworz={setKarta}
        dodajDoPorownania={(id) => {
          const lista = wybraniPozycji.includes(id) ? wybraniPozycji : [...wybraniPozycji, id].slice(-4);
          setWybrani({ ...wybrani, [pozycja]: lista });
        }}
      />
    </AppShell>
  );
}
