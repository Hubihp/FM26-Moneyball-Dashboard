import { Alert, Box, Button, Chip, Group, Loader, Stack, Switch, Text } from '@mantine/core';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { useState } from 'react';

import { api, type Wiersz, type ZapytanieRankingu } from '../api';
import TabelaRankingu from './TabelaRankingu';

const OPISY: Record<string, string> = {
  'niedowartościowany': 'gra jak zawodnik co najmniej 2 razy droższy (SCORE ≥ 55)',
  'kontrakt ≤ 6 mies.': 'może podpisać przedkontrakt z klubem zagranicznym',
  'kontrakt ≤ 12 mies.': 'klub sprzeda taniej, zanim straci go za darmo',
  'wolny agent': 'bez klubu - koszt to tylko pensja',
  'koniec wypożyczenia': 'wypożyczenie kończy się w ciągu pół roku',
  'talent bez minut': 'do 21 lat, duży klub, mniej niż 900 minut - kandydat do wypożyczenia',
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
  porownaj: (ids: string[]) => void;
};

// Ranking zawodnikow z okazjami transferowymi (filtry z panelu bocznego dalej obowiazuja).
// Ten sam znacznik z kolumny "Okazje" (analiza.wzbogac) - zadnych innych, ukrytych warunkow.
export default function Okazje({ zapytanie, okazje, wersja, mojKlubUid, naWybor, ulubione, przelaczUlubione, wybrane,
  setWybrane, pominMoj, setPominMoj, porownaj }: Props) {
  const [zaznaczeni, setZaznaczeni] = useState<string[]>([]);
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
          <Group justify="space-between">
            <Text size="sm">Znaleziono: {ranking.data.liczba}</Text>
            <Button size="xs" variant="light" disabled={!zaznaczeni.length} onClick={() => porownaj(zaznaczeni)}>
              Porównaj zaznaczonych ({zaznaczeni.length}{zaznaczeni.length > 4 ? ', pierwszych 4' : ''})
            </Button>
          </Group>
          <Box style={{ flex: 1, minHeight: 300 }}>
            <TabelaRankingu kolumny={ranking.data.kolumny} wiersze={ranking.data.wiersze} mojKlubUid={mojKlubUid}
              naWybor={naWybor} ulubione={ulubione} przelaczUlubione={przelaczUlubione} naZaznaczenie={setZaznaczeni} />
          </Box>
        </>
      )}
    </Stack>
  );
}
