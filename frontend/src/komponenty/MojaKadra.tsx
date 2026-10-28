import { Alert, Badge, Button, Card, Group, Loader, SegmentedControl, SimpleGrid, Stack, Switch, Table, Text, Title } from '@mantine/core';
import { useQuery, type UseQueryResult } from '@tanstack/react-query';
import { lazy, Suspense, useState } from 'react';

import { api, type Filtry, type Kadra, type Wiersz, type ZapytanieRankingu } from '../api';
import { formatuj } from '../format';
import { usePamiec } from '../pamiec';
import Nastepca from './Nastepca';
import type { Ustawienia } from './PanelBoczny';

const SprzedajDrogo = lazy(() => import('./SprzedajDrogo'));
const Optymalizator = lazy(() => import('./Optymalizator'));
const Taktyka = lazy(() => import('./Taktyka'));

type Props = {
  wersja: number;
  wagi: Record<string, Record<string, number>>;
  ustawienia: Ustawienia;
  szukajNastepcy: (pozycja: string) => void;
  otworz: (pozycja: string, id: string, wiersz?: Wiersz) => void;
  zapytanieDla: (pozycja: string) => ZapytanieRankingu;
  mojKlubUid: number | null | undefined;
  filtry: Filtry;                 // wspolne filtry panelu (zastepcy, kandydaci optymalizatora)
  ulubione: Set<string>;
  przelaczUlubione: (wiersz: Wiersz, pozycja: string) => void;
};

// Analiza kadry: moi zawodnicy na kazdej pozycji, od bramkarza do napastnika
export default function MojaKadra(p: Props) {
  const { wersja, wagi, ustawienia, otworz } = p;
  const [widok, setWidok] = usePamiec('fm-kadra-widok', 'pozycje');
  // domyslnie tylko seniorska pierwsza druzyna (bez rezerw, druzyn B i juniorow)
  const [tylkoPierwsza, setTylkoPierwsza] = usePamiec('fm-tylko-pierwsza', true);
  const kadra = useQuery({
    queryKey: ['kadra', wersja, wagi, ustawienia.k_baza, ustawienia.ignoruj_mnoznik, tylkoPierwsza],
    queryFn: () => api.mojaKadra({ wagi, ignoruj_mnoznik: ustawienia.ignoruj_mnoznik, k_baza: ustawienia.k_baza,
      tylko_pierwsza: tylkoPierwsza }),
  });
  const zapytanie = { wagi, ignoruj_mnoznik: ustawienia.ignoruj_mnoznik, k_baza: ustawienia.k_baza, filtry: p.filtry,
    tylko_pierwsza: tylkoPierwsza };
  const ukryci = Math.max(0, ...(kadra.data?.pozycje ?? []).map((x) => x.ukryci ?? 0));

  return (
    <Stack p="md" gap="sm">
      <Group justify="space-between">
        <SegmentedControl w="fit-content" value={widok} onChange={setWidok} data={[
          { value: 'pozycje', label: 'Pozycje' },
          { value: 'taktyka', label: 'Taktyka' },
          { value: 'sprzedaj', label: 'Sprzedaj drogo' },
          { value: 'optymalizator', label: 'Optymalizator budżetu' },
        ]} />
        <Switch label="Tylko pierwsza drużyna" checked={tylkoPierwsza}
          description={tylkoPierwsza && ukryci ? 'ukryto zawodników rezerw i juniorów' : undefined}
          onChange={(e) => setTylkoPierwsza(e.currentTarget.checked)} />
      </Group>
      <Suspense fallback={<Loader size="sm" />}>
        {widok === 'taktyka' ? (
          <Taktyka wersja={wersja} wagi={wagi} ustawienia={ustawienia} tylkoPierwsza={tylkoPierwsza}
            otworz={(poz, id) => otworz(poz, id)} />
        ) : widok === 'sprzedaj' ? (
          <SprzedajDrogo zapytanie={zapytanie} wersja={wersja} otworz={otworz} ulubione={p.ulubione}
            przelaczUlubione={p.przelaczUlubione} />
        ) : widok === 'optymalizator' ? (
          kadra.data ? (
            <Optymalizator zapytanie={zapytanie} wersja={wersja} kadra={kadra.data.pozycje}
              pozycje={kadra.data.pozycje.map((x) => x.pozycja)} otworz={otworz} ulubione={p.ulubione}
              przelaczUlubione={p.przelaczUlubione} />
          ) : kadra.error ? <Alert color="red">{(kadra.error as Error).message}</Alert> : <Loader size="sm" />
        ) : (
          <WidokPozycji {...p} kadra={kadra} />
        )}
      </Suspense>
    </Stack>
  );
}

type PropsPozycji = Props & { kadra: UseQueryResult<Kadra> };

// Kazda pozycja mojego klubu na tle puli, od bramkarza do napastnika
function WidokPozycji({ wersja, szukajNastepcy, otworz, zapytanieDla, mojKlubUid, kadra }: PropsPozycji) {
  const [nastepcaDla, setNastepcaDla] = useState<{ pozycja: string; id: string; pilkarz: string } | null>(null);
  if (kadra.isLoading) return <Loader m="md" />;
  if (kadra.error) return <Alert m="md" color="red">{(kadra.error as Error).message}</Alert>;
  if (!kadra.data) return null;
  const pozycje = kadra.data.pozycje;

  return (
    <Stack>
      <Text size="sm" c="dimmed">
        Pozycje od bramkarza do napastnika. Twoi zawodnicy są liczeni nawet poniżej progu minut, więc przy małej liczbie
        minut ich wynik jest mniej pewny.
      </Text>
      <SimpleGrid cols={{ base: 1, lg: 2 }}>
        {pozycje.map((p) => (
          <Card key={p.pozycja} withBorder padding="sm">
            <Group justify="space-between" mb="xs">
              <Title order={5}>{p.pozycja}</Title>
              {p.liczba === 0 && <Badge color="red" variant="light" size="lg">brak zawodnika</Badge>}
            </Group>
            <Group gap="xs" mb="xs">
              <Badge variant="outline" color="gray">zawodników: {p.liczba}</Badge>
              <Badge variant="outline" color="gray">najlepszy: {formatuj(p.najlepszy, 'score')}</Badge>
              <Badge variant="outline" color="gray">śr. wiek: {formatuj(p.sredni_wiek, 'dec1')}</Badge>
              {p.konczace_kontrakty > 0 && (
                <Badge variant="light" color="orange">kontrakt ≤ 12 mies.: {p.konczace_kontrakty}</Badge>
              )}
            </Group>
            {p.zawodnicy.length > 0 ? (
              <Table striped highlightOnHover fz="sm">
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Piłkarz</Table.Th><Table.Th>Wiek</Table.Th><Table.Th>SCORE</Table.Th>
                    <Table.Th>Minuty</Table.Th><Table.Th>Kontrakt do</Table.Th><Table.Th />
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {p.zawodnicy.map((z) => (
                    <Table.Tr key={String(z['ID'])} style={{ cursor: 'pointer' }} onClick={() => otworz(p.pozycja, String(z['ID']), z)}>
                      <Table.Td>
                        <Text size="sm" fw={600}>
                          {String(z['Piłkarz'])}{' '}
                          {z['Drużyna'] && z['Drużyna'] !== 'Pierwsza drużyna' ? (
                            <Badge size="xs" color="gray" variant="light">{String(z['Drużyna'])}</Badge>
                          ) : null}
                        </Text>
                        {z['Pozycja'] ? <Text size="xs" c="dimmed">pozycje: {String(z['Pozycja'])}</Text> : null}
                      </Table.Td>
                      <Table.Td>{formatuj(z['Wiek'], 'int')}</Table.Td>
                      <Table.Td>{formatuj(z['SCORE'], 'score')}</Table.Td>
                      <Table.Td>{formatuj(z['Minuty'], 'int')}</Table.Td>
                      <Table.Td c={typeof z['Lata_kontraktu'] === 'number' && z['Lata_kontraktu'] <= 1 ? 'orange' : undefined}>
                        {formatuj(z['Wygasa_Data'], 'data')}
                      </Table.Td>
                      <Table.Td>
                        <Button size="compact-xs" variant="light" title="Zawodnicy o najbardziej podobnym stylu gry"
                          onClick={(e) => {
                            e.stopPropagation();
                            setNastepcaDla({ pozycja: p.pozycja, id: String(z['ID']), pilkarz: String(z['Piłkarz']) });
                          }}>
                          Następca
                        </Button>
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            ) : (
              <Text size="sm" c="dimmed">Brak zawodników na tej pozycji.</Text>
            )}
            <Button mt="sm" variant="light" size="xs" onClick={() => szukajNastepcy(p.pozycja)}>
              Szukaj wzmocnienia
            </Button>
          </Card>
        ))}
      </SimpleGrid>
      <Nastepca zawodnik={nastepcaDla} zapytanie={nastepcaDla ? zapytanieDla(nastepcaDla.pozycja) : null} wersja={wersja}
        mojKlubUid={mojKlubUid} zamknij={() => setNastepcaDla(null)}
        otworz={(poz, id, w) => {
          setNastepcaDla(null);
          otworz(poz, id, w);
        }} />
    </Stack>
  );
}
