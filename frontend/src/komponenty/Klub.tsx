import { Alert, Badge, Card, Group, Loader, SegmentedControl, SimpleGrid, Stack, Table, Text, Title, Tooltip } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';

import { api, type OsobaPersonelu } from '../api';
import { eur, formatuj } from '../format';
import Wykres from './Wykres';

const KOLOR_STATUSU: Record<string, string> = { ok: 'teal', uwaga: 'yellow', 'błąd': 'red' };

function Liczba({ etykieta, wartosc, opis, kolor }: { etykieta: string; wartosc: string; opis?: string; kolor?: string }) {
  const tresc = (
    <Stack gap={0}>
      <Text size="xs" c="dimmed">{etykieta}</Text>
      <Text size="lg" fw={700} c={kolor}>{wartosc}</Text>
    </Stack>
  );
  return opis ? <Tooltip multiline w={320} label={opis}><div>{tresc}</div></Tooltip> : tresc;
}

const miesiac = (iso: string) => {
  const [r, m] = iso.split('-');
  return `${m}.${r}`;
};

function Finanse({ wersja }: { wersja: number }) {
  const dane = useQuery({ queryKey: ['finanse', wersja], queryFn: api.finanse });
  if (dane.isLoading) return <Loader />;
  if (dane.error) return <Alert color="red">{(dane.error as Error).message}</Alert>;
  const f = dane.data;
  if (!f?.ma_dane || !f.podsumowanie) {
    return <Alert color="gray">Finanse wymagają zapisu gry z Twoim klubem (przy CSV i danych demo ich nie ma).</Alert>;
  }
  const p = f.podsumowanie;
  const m = f.miesiace;
  return (
    <Stack gap="md">
      <Card withBorder>
        <SimpleGrid cols={{ base: 2, md: 6 }}>
          <Liczba etykieta="Saldo" wartosc={eur(p.saldo)} kolor={(p.saldo ?? 0) < 0 ? 'red' : undefined} />
          <Liczba etykieta={`Przychody (${p.miesiecy} mies.)`} wartosc={eur(p.przychody)}
            opis="Bez transferów: bilety, prawa telewizyjne, sponsorzy, nagrody i inne." />
          <Liczba etykieta={`Wydatki (${p.miesiecy} mies.)`} wartosc={eur(p.wydatki)} opis="Bez transferów, z płacami." />
          <Liczba etykieta="Wynik bez transferów / mies." wartosc={eur(p.wynik_operacyjny_miesiac)}
            kolor={(p.wynik_operacyjny_miesiac ?? 0) < 0 ? 'red' : 'teal'} />
          <Liczba etykieta="Prognoza salda za 12 mies." wartosc={eur(p.prognoza_salda_12)}
            kolor={(p.prognoza_salda_12 ?? 0) < 0 ? 'red' : undefined}
            opis="Saldo dziś + 12 × średni miesięczny wynik bez transferów z ostatnich 12 miesięcy. Sprzedaże i zakupy zawodników zmienią ten wynik." />
          <Liczba etykieta="Płace / przychody" wartosc={p.udzial_plac === null ? '–' : `${Math.round(p.udzial_plac * 100)}%`}
            kolor={p.status_plac ? KOLOR_STATUSU[p.status_plac] : undefined}
            opis={`Roczne płace zawodników (${eur(p.place_rocznie)}: tygodniowa lista płac × 52) wobec rocznych przychodów bez transferów (${eur(p.przychody_rocznie)}). Powyżej ${Math.round(p.prog_plac * 100)}% klub zwykle traci pieniądze; UEFA dopuszcza koszty kadry do 70% przychodów.`} />
        </SimpleGrid>
        <Group gap="xl" mt="sm">
          <Text size="sm">Płace: <b>{eur(p.place_tydzien)}</b> / tydz. z budżetu <b>{eur(p.budzet_plac_tydzien)}</b>
            {p.place_tydzien !== null && p.budzet_plac_tydzien !== null
              ? ` (wolne ${eur(Math.max(0, p.budzet_plac_tydzien - p.place_tydzien))})` : ''}</Text>
          <Text size="sm">Budżet transferowy: <b>{eur(p.budzet_transferowy)}</b></Text>
          <Text size="sm">Transfery ({p.miesiecy} mies.): <b style={{ color: (p.transfery ?? 0) < 0 ? '#ff8787' : '#69db7c' }}>
            {(p.transfery ?? 0) > 0 ? '+' : ''}{eur(p.transfery)}</b></Text>
        </Group>
      </Card>
      <Wykres
        wysokosc={300}
        opcje={{
          tooltip: { trigger: 'axis', valueFormatter: (v) => eur(v as number) },
          legend: { top: 0 },
          grid: { left: 80, right: 80, top: 35, bottom: 30 },
          xAxis: { type: 'category', data: m.map((x) => miesiac(x.miesiac)) },
          yAxis: [
            { type: 'value', name: 'Miesiąc', axisLabel: { formatter: (v: number) => eur(v) } },
            { type: 'value', name: 'Saldo', axisLabel: { formatter: (v: number) => eur(v) } },
          ],
          series: [
            { name: 'Przychody', type: 'bar', data: m.map((x) => x.przychody), color: '#69db7c' },
            { name: 'Wydatki', type: 'bar', data: m.map((x) => x.wydatki), color: '#ff8787' },
            { name: 'Płace', type: 'line', data: m.map((x) => x.place), color: '#fcc419' },
            { name: 'Saldo', type: 'line', yAxisIndex: 1, data: m.map((x) => x.saldo), color: '#74c0fc', lineStyle: { width: 3 } },
          ],
        }}
      />
      {f.wygasajace.length > 0 && (
        <>
          <Title order={6}>Kontrakty wygasające w ciągu 12 miesięcy</Title>
          <Text size="xs" c="dimmed">
            Ich płace ({eur(f.wygasajace.reduce((a, x) => a + (x.Płaca_tydzien ?? 0), 0))} / tydz.) zwolnią się
            z budżetu, jeśli nie przedłużysz umów.
          </Text>
          <Table striped withTableBorder fz="xs" maw={640}>
            <Table.Thead>
              <Table.Tr><Table.Th>Piłkarz</Table.Th><Table.Th ta="right">Wiek</Table.Th><Table.Th>Wygasa</Table.Th>
                <Table.Th ta="right">Płaca / tydz.</Table.Th></Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {f.wygasajace.map((x) => (
                <Table.Tr key={x.Piłkarz + x.Wygasa}>
                  <Table.Td>{x.Piłkarz}</Table.Td><Table.Td ta="right">{x.Wiek ?? '–'}</Table.Td>
                  <Table.Td>{formatuj(x.Wygasa, 'data')}</Table.Td><Table.Td ta="right">{eur(x.Płaca_tydzien)}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </>
      )}
      <Text size="xs" c="dimmed">
        Dane miesięczne z zapisu gry. Znaczenie części pól (przychody, wydatki, płace, transfery) biblioteka fmsave
        oznacza jako niepotwierdzone; saldo, lista płac i budżety są potwierdzone.
      </Text>
    </Stack>
  );
}

const ocenaKolor = (x: number | null | undefined) =>
  x === null || x === undefined ? undefined : x >= 16 ? '#69db7c' : x >= 12 ? undefined : '#ff8787';

function TabelaOsob({ osoby, obszar, zKlubem }: { osoby: OsobaPersonelu[]; obszar?: string; zKlubem?: boolean }) {
  return (
    <Table striped highlightOnHover withTableBorder fz="xs">
      <Table.Thead>
        <Table.Tr>
          <Table.Th>Osoba</Table.Th>
          {zKlubem && <Table.Th>Klub</Table.Th>}
          <Table.Th>Stanowisko</Table.Th>
          <Table.Th ta="right">Wiek</Table.Th>
          <Table.Th>{obszar ? `Ocena: ${obszar}` : 'Najlepszy obszar'}</Table.Th>
          <Table.Th ta="right">Płaca / tydz.</Table.Th>
          <Table.Th>Kontrakt do</Table.Th>
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {osoby.map((o) => {
          const ocena = obszar ? o.oceny[obszar] : o.najlepsza_ocena;
          return (
            <Table.Tr key={o.uid}>
              <Table.Td>{o.nazwa}{o.druzyna ? <Badge ml={6} size="xs" variant="light" color="gray">młodzież / rezerwy</Badge> : null}</Table.Td>
              {zKlubem && <Table.Td>{o.klub}</Table.Td>}
              <Table.Td>{o.stanowisko}</Table.Td>
              <Table.Td ta="right">{o.wiek ?? '–'}</Table.Td>
              <Table.Td>
                <b style={{ color: ocenaKolor(ocena) }}>{ocena === null || ocena === undefined ? '–' : formatuj(ocena, 'dec1')}</b>
                {!obszar && o.najlepszy_obszar ? ` · ${o.najlepszy_obszar}` : ''}
              </Table.Td>
              <Table.Td ta="right">{eur(o.placa_tydzien)}</Table.Td>
              <Table.Td>{formatuj(o.kontrakt_do, 'data')}</Table.Td>
            </Table.Tr>
          );
        })}
      </Table.Tbody>
    </Table>
  );
}

function Personel({ wersja }: { wersja: number }) {
  const dane = useQuery({ queryKey: ['personel', wersja], queryFn: api.personel, staleTime: Infinity, retry: false });
  if (dane.isLoading) {
    return (
      <Group gap="sm"><Loader size="sm" /><Text size="sm">Odczyt personelu z zapisu gry (ok. 20 s, tylko za pierwszym razem)...</Text></Group>
    );
  }
  if (dane.error) return <Alert color="red">{(dane.error as Error).message}</Alert>;
  const p = dane.data;
  if (!p) return null;
  const luki = p.obszary.filter((o) => o.luka);
  return (
    <Stack gap="md">
      <Title order={6}>Sztab na tle ligi ({p.liga_klubow} klubów)</Title>
      <Text size="xs" c="dimmed">
        Ocena obszaru: najlepsza osoba pierwszej drużyny w danym obszarze, w skali 1-20 (średnia atrybutów obszaru);
        liga - najlepsi w każdym klubie ligi. Luka: poniżej mediany ligi.
      </Text>
      <Table withTableBorder fz="sm" maw={900}>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Obszar</Table.Th><Table.Th ta="right">Twój sztab</Table.Th><Table.Th>Kto</Table.Th>
            <Table.Th ta="right">Mediana ligi</Table.Th><Table.Th ta="right">Najlepszy w lidze</Table.Th>
            <Table.Th ta="right">Miejsce</Table.Th><Table.Th />
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {p.obszary.map((o) => (
            <Table.Tr key={o.obszar}>
              <Table.Td>
                <Tooltip label={`Atrybuty: ${(p.obszary_opis[o.obszar] ?? []).join(', ')}`}><span>{o.obszar}</span></Tooltip>
              </Table.Td>
              <Table.Td ta="right"><b style={{ color: ocenaKolor(o.moja) }}>{formatuj(o.moja, 'dec1')}</b></Table.Td>
              <Table.Td>{o.kto ?? 'brak osoby'}</Table.Td>
              <Table.Td ta="right">{formatuj(o.mediana_ligi, 'dec1')}</Table.Td>
              <Table.Td ta="right">{formatuj(o.najlepsza_ligi, 'dec1')}</Table.Td>
              <Table.Td ta="right">{o.miejsce ? `${o.miejsce}/${o.klubow}` : '–'}</Table.Td>
              <Table.Td>{o.luka ? <Badge color="red" variant="light">luka</Badge> : null}</Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
      {luki.map((o) => (p.kandydaci[o.obszar] ?? []).length > 0 && (
        <Stack key={o.obszar} gap={4}>
          <Title order={6}>Kandydaci: {o.obszar} (lepsi niż Twój sztab)</Title>
          <TabelaOsob osoby={p.kandydaci[o.obszar]} obszar={o.obszar} zKlubem />
        </Stack>
      ))}
      <Title order={6}>Twój sztab ({p.sztab.length} osób)</Title>
      <TabelaOsob osoby={p.sztab} />
      <Text size="xs" c="dimmed">
        Atrybuty personelu biblioteka fmsave czyta w skali 1-100 i oznacza jako niepotwierdzone; program dzieli je przez 5
        (gra pokazuje 1-20). Pomija zarząd i lekarzy. Najlepszy obszar osoby liczy się tylko z obszarów jej stanowiska.
      </Text>
    </Stack>
  );
}

export default function Klub({ wersja }: { wersja: number }) {
  const [widok, setWidok] = useState<'finanse' | 'personel'>('finanse');
  return (
    <Stack p="md" gap="md">
      <SegmentedControl w="fit-content" value={widok} onChange={(v) => setWidok(v as 'finanse' | 'personel')}
        data={[{ value: 'finanse', label: 'Finanse' }, { value: 'personel', label: 'Personel' }]} />
      {widok === 'finanse' ? <Finanse wersja={wersja} /> : <Personel wersja={wersja} />}
    </Stack>
  );
}
