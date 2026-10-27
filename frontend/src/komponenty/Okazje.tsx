import { Alert, Box, Chip, Group, Loader, Stack, Switch, Text } from '@mantine/core';
import { keepPreviousData, useQuery } from '@tanstack/react-query';

import { api, type Wiersz, type ZapytanieRankingu } from '../api';
import TabelaRankingu from './TabelaRankingu';

const OPISY: Record<string, string> = {
  'niedowartościowany': 'gra jak zawodnik co najmniej 2 razy droższy (SCORE ≥ 55)',
  'kontrakt ≤ 6 mies.': 'może podpisać przedkontrakt z klubem zagranicznym',
  'kontrakt ≤ 12 mies.': 'klub sprzeda taniej, zanim straci go za darmo',
  'szybki rozwój': 'do 23 lat, SCORE wyższy o co najmniej 5 niż w poprzednim sezonie (z historii zapisów)',
};

type Props = {
  zapytanie: ZapytanieRankingu;
  okazje: string[];
  wersja: number;
  mojKlubUid: number | null | undefined;
  naWybor: (id: string, wiersz?: Wiersz) => void;
  ulubione: Set<string>;
  przelaczUlubione: (wiersz: Wiersz) => void;
  // wybor okazji i "pomin moj klub" sa trzymane w App (wspolne dla pozycji, zapamietane)
  wybrane: string[];
  setWybrane: (v: string[]) => void;
  pominMoj: boolean;
  setPominMoj: (v: boolean) => void;
  zaznaczeni: string[];
  naZaznaczenie: (ids: string[], wszystkie: string[]) => void;
};

// Ranking zawodnikow z okazjami transferowymi (filtry z panelu bocznego dalej obowiazuja).
// Ten sam znacznik z kolumny "Okazje" (analiza.wzbogac) - zadnych innych, ukrytych warunkow.
export default function Okazje({ zapytanie, okazje, wersja, mojKlubUid, naWybor, ulubione, przelaczUlubione, wybrane,
  setWybrane, pominMoj, setPominMoj, zaznaczeni, naZaznaczenie }: Props) {
  const znane = wybrane.filter((o) => okazje.includes(o));
  const pelne: ZapytanieRankingu = {
    ...zapytanie,
    filtry: { ...zapytanie.filtry, okazje: znane, tylko_z_okazja: true, bez_mojego_klubu: pominMoj },
  };
  const ranking = useQuery({
    queryKey: ['okazje', wersja, pelne],
    queryFn: () => api.ranking(pelne),
    placeholderData: keepPreviousData,
  });
  const ukryci = ranking.data?.liczba_ukrytych_mojego_klubu ?? 0;

  return (
    <Stack p="sm" h="100%" gap="xs">
      <Chip.Group multiple value={wybrane} onChange={setWybrane}>
        <Group gap="xs">
          {okazje.map((o) => (
            <Chip key={o} value={o} size="sm" title={OPISY[o]}>{o}</Chip>
          ))}
          {ranking.isFetching && <Loader size="xs" />}
        </Group>
      </Chip.Group>
      <Text size="xs" c="dimmed">
        {znane.length
          ? znane.map((o) => `${o}: ${OPISY[o] ?? ''}`).join(' · ') + '.'
          : 'Nic nie zaznaczono - lista pokazuje zawodników z dowolną okazją. Zaznacz rodzaje okazji, aby zawęzić listę.'}
        {' '}Filtry z lewego panelu nadal działają. Zawodnik pojawia się tu wtedy i tylko wtedy, gdy ma dany znacznik
        w kolumnie „Okazje” rankingu.
      </Text>
      {mojKlubUid !== null && mojKlubUid !== undefined && (
        <Group gap="xs">
          <Switch size="xs" checked={pominMoj} onChange={(e) => setPominMoj(e.currentTarget.checked)}
            label="Pomiń zawodników mojego klubu" />
          {pominMoj && ukryci > 0 && (
            <Text size="xs" c="dimmed">(ukryto {ukryci} z twojego klubu)</Text>
          )}
        </Group>
      )}
      {ranking.error && <Alert color="red">{(ranking.error as Error).message}</Alert>}
      {ranking.data && (
        <>
          <Text size="sm">
            Znaleziono: {ranking.data.liczba}
            <Text span size="xs" c="dimmed"> · kliknij nazwisko, aby otworzyć kartę · zaznacz do 4 zawodników do porównania</Text>
          </Text>
          <Box style={{ flex: 1, minHeight: 300 }}>
            <TabelaRankingu kolumny={ranking.data.kolumny} wiersze={ranking.data.wiersze} mojKlubUid={mojKlubUid}
              naWybor={naWybor} ulubione={ulubione} przelaczUlubione={przelaczUlubione}
              zaznaczeni={zaznaczeni} naZaznaczenie={naZaznaczenie} kluczUkladu={`okazje|${zapytanie.pozycja}`} />
          </Box>
        </>
      )}
    </Stack>
  );
}
