import { Alert, Badge, Group, Loader, Stack, Table, Text, Title } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';

import { api, type PorownanieZMoim, type ZapytanieRankingu } from '../api';
import { formatuj } from '../format';

type Props = { id: string; zapytanie: ZapytanieRankingu; wersja: number; mojKlub: string | null | undefined };

const WERDYKT: Record<string, { kolor: string; tekst: string }> = {
  wzmocnienie: { kolor: 'teal', tekst: 'Wzmocnienie' },
  'podobny poziom': { kolor: 'gray', tekst: 'Podobny poziom' },
  'nie wzmacnia': { kolor: 'red', tekst: 'Nie wzmacnia' },
  'brak zawodnika': { kolor: 'teal', tekst: 'Wzmocnienie - nie masz nikogo na tej pozycji' },
};

const LEPSZY = { backgroundColor: 'rgba(64, 192, 87, 0.22)', fontWeight: 600 };

// Kandydat na tle najlepszego zawodnika mojego klubu (z biezacego zapisu) na tej samej pozycji
export default function NaTleMojego({ id, zapytanie, wersja, mojKlub }: Props) {
  const dane = useQuery({
    queryKey: ['porownanie-z-moim', wersja, zapytanie.pozycja, id, zapytanie.wagi, zapytanie.k_baza,
      zapytanie.ignoruj_mnoznik],
    queryFn: () => api.porownanieZMoim({ ...zapytanie, id }),
  });
  if (!mojKlub) return null;
  const naglowek = <Title order={5}>Na tle twojego zawodnika ({mojKlub})</Title>;
  if (dane.isLoading) return <Stack gap="xs">{naglowek}<Loader size="sm" /></Stack>;
  if (dane.error) return <Alert color="red">{(dane.error as Error).message}</Alert>;
  const p = dane.data as PorownanieZMoim;
  if (!p || p.werdykt === 'twój zawodnik' || p.werdykt === 'nieznany klub') return null;
  const werdykt = p.werdykt ? WERDYKT[p.werdykt] : undefined;

  return (
    <Stack gap="xs">
      {naglowek}
      <Group gap="sm">
        {werdykt && <Badge size="md" color={werdykt.kolor} variant="filled">{werdykt.tekst}</Badge>}
        {p.moj && (
          <Text size="sm">
            twój najlepszy na pozycji {zapytanie.pozycja}: <b>{String(p.moj['Piłkarz'])}</b> (SCORE{' '}
            {formatuj(p.moj['SCORE'], 'score')}) · różnica SCORE: <b>{formatuj(p.roznica, 'zmiana')}</b>
          </Text>
        )}
      </Group>
      {p.moj && (
        <>
          <Table withTableBorder fz="xs">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Kluczowa statystyka</Table.Th>
                <Table.Th ta="right">Kandydat</Table.Th>
                <Table.Th ta="right">{String(p.moj['Piłkarz'])}</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {p.cechy.map((c) => (
                <Table.Tr key={c.nazwa}>
                  <Table.Td>{c.nazwa}{c.nizsze_lepsze ? ' (mniej = lepiej)' : ''}</Table.Td>
                  <Table.Td ta="right" style={c.lepszy === 'kandydat' ? LEPSZY : undefined}>
                    {formatuj(c.kandydat, 'dec2')}
                    <Text span size="xs" c="dimmed"> ({formatuj(c.percentyl_kandydata, 'int')})</Text>
                  </Table.Td>
                  <Table.Td ta="right" style={c.lepszy === 'moj' ? LEPSZY : undefined}>
                    {formatuj(c.moj, 'dec2')}
                    <Text span size="xs" c="dimmed"> ({formatuj(c.percentyl_moj, 'int')})</Text>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
          <Text size="xs" c="dimmed">
            Statystyki z wagami tej pozycji; w nawiasie percentyl w pozycji, na zielono lepszy z dwóch. Wzmocnienie = SCORE
            wyższy o co najmniej 3, podobny poziom = różnica poniżej 3.
          </Text>
        </>
      )}
    </Stack>
  );
}
