import { Alert, Box, Chip, Group, Loader, Stack, Text } from '@mantine/core';
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
};

// Ranking zawodnikow z okazjami transferowymi (filtry z panelu bocznego dalej obowiazuja)
export default function Okazje({ zapytanie, okazje, wersja, mojKlubUid, naWybor, ulubione, przelaczUlubione }: Props) {
  const [wybrane, setWybrane] = useState<string[]>(okazje.filter((o) => o !== 'kontrakt ≤ 6 mies.'));
  const pelne: ZapytanieRankingu = {
    ...zapytanie,
    filtry: { ...zapytanie.filtry, okazje: wybrane, bez_mojego_klubu: true },
  };
  const ranking = useQuery({
    queryKey: ['okazje', wersja, pelne],
    queryFn: () => api.ranking(pelne),
    enabled: wybrane.length > 0,
    placeholderData: keepPreviousData,
  });

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
        {wybrane.map((o) => `${o}: ${OPISY[o] ?? ''}`).join(' · ')}. Bez zawodników twojego klubu; filtry z lewego panelu
        nadal działają. Kolumna „Opłacalność” = punkty SCORE ponad przeciętnego na 1 mln € kosztu (cena + 3 lata pensji).
      </Text>
      {wybrane.length === 0 && <Alert color="gray">Zaznacz co najmniej jeden rodzaj okazji.</Alert>}
      {ranking.error && <Alert color="red">{(ranking.error as Error).message}</Alert>}
      {ranking.data && wybrane.length > 0 && (
        <>
          <Text size="sm">Znaleziono: {ranking.data.liczba}</Text>
          <Box style={{ flex: 1, minHeight: 300 }}>
            <TabelaRankingu kolumny={ranking.data.kolumny} wiersze={ranking.data.wiersze} mojKlubUid={mojKlubUid}
              naWybor={naWybor} ulubione={ulubione} przelaczUlubione={przelaczUlubione} />
          </Box>
        </>
      )}
    </Stack>
  );
}
