import { Alert, Box, Button, Group, Loader, Stack, Text } from '@mantine/core';
import { keepPreviousData, useQuery } from '@tanstack/react-query';

import { api, type Wiersz } from '../api';
import { kluczZawodnika, type WpisListy } from '../pamiec';
import type { Ustawienia } from './PanelBoczny';
import TabelaRankingu from './TabelaRankingu';

type Props = {
  lista: WpisListy[];
  setLista: (lista: WpisListy[]) => void;
  wersja: number;
  wagi: Record<string, Record<string, number>>;
  ustawienia: Ustawienia;
  mojKlubUid: number | null | undefined;
  naWybor: (pozycja: string, id: string, wiersz: Wiersz) => void;
  pozycja: string;
  zaznaczeni: string[];
  naZaznaczenie: (ids: string[], wszystkie: string[]) => void;
};

// Zawodnicy oznaczeni gwiazdka - z aktualnym wynikiem w pozycji, z ktorej zostali dodani
export default function ListaZyczen({ lista, setLista, wersja, wagi, ustawienia, mojKlubUid, naWybor, pozycja,
  zaznaczeni, naZaznaczenie }: Props) {
  const zapytanie = {
    wpisy: lista.map((w) => ({ klucz: w.klucz, pozycja: w.pozycja, pilkarz: w.pilkarz })),
    wagi,
    ignoruj_mnoznik: ustawienia.ignoruj_mnoznik,
    k_baza: ustawienia.k_baza,
  };
  const dane = useQuery({
    queryKey: ['lista-zyczen', wersja, zapytanie],
    queryFn: () => api.listaZyczen(zapytanie),
    enabled: lista.length > 0,
    placeholderData: keepPreviousData,
  });

  if (lista.length === 0) {
    return (
      <Alert m="md" color="gray" title="Lista życzeń jest pusta">
        Kliknij gwiazdkę przy zawodniku w rankingu, w okazjach albo w karcie zawodnika, aby dodać go do listy.
        Lista jest zapamiętywana w tej przeglądarce, także po zamknięciu aplikacji.
      </Alert>
    );
  }

  const nieznalezieni = lista.filter((w) => dane.data?.nieznalezieni.includes(w.klucz));
  const ulubione = new Set(lista.map((w) => w.klucz));

  return (
    <Stack p="sm" h="100%" gap="xs">
      <Group justify="space-between">
        <Text size="sm">
          Zawodników na liście: {lista.length}. Wynik liczony w pozycji, z której zawodnik został dodany, z bieżącymi
          wagami. Gwiazdka usuwa z listy. Zaznacz do 4 zawodników do porównania (na tle pozycji {pozycja}).
        </Text>
        <Group gap="xs">
          {dane.isFetching && <Loader size="xs" />}
          <Button size="xs" variant="subtle" color="red" onClick={() => setLista([])}>Wyczyść listę</Button>
        </Group>
      </Group>
      {dane.error && <Alert color="red">{(dane.error as Error).message}</Alert>}
      {nieznalezieni.length > 0 && (
        <Alert color="yellow" title="Nie znaleziono w obecnych danych">
          <Text size="sm">
            {nieznalezieni.map((w) => `${w.pilkarz} (${w.klub}, ${w.pozycja})`).join(', ')} - np. po wczytaniu innego
            zapisu albo gdy zawodnik nie spełnia już progu minut.
          </Text>
          <Button mt="xs" size="xs" variant="light" color="yellow"
            onClick={() => setLista(lista.filter((w) => !nieznalezieni.includes(w)))}>
            Usuń nieznalezionych z listy
          </Button>
        </Alert>
      )}
      {dane.data && (
        <Box style={{ flex: 1, minHeight: 300 }}>
          <TabelaRankingu
            kolumny={dane.data.kolumny}
            wiersze={dane.data.wiersze}
            mojKlubUid={mojKlubUid}
            naWybor={(id, w) => w && naWybor(String(w['Pozycja na liście']), id, w)}
            ulubione={ulubione}
            przelaczUlubione={(w) => setLista(lista.filter((x) => x.klucz !== kluczZawodnika(w)))}
            zaznaczeni={zaznaczeni}
            naZaznaczenie={naZaznaczenie}
            kluczUkladu="lista"
          />
        </Box>
      )}
    </Stack>
  );
}
