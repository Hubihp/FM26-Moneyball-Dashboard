import { Alert, Badge, Card, Group, Loader, SegmentedControl, Select, SimpleGrid, Stack, Table, Text, Title, Tooltip } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';

import { api, type MiesiacFinansow, type ObszarSztabu, type OsobaPersonelu } from '../api';
import { eur, formatuj } from '../format';
import { SZEROKOSC } from '../wyglad';
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

// Kwoty na osiach i w podpowiedziach krotko: "12,3 mln €", "-850 tys. €"
const kwota = (v: number | null | undefined) => (v === null || v === undefined ? '–' : eur(v));

// Dwa panele ze wspolna osia miesiecy: u gory przeplywy miesiaca (przychody w gore, wydatki w dol, transfery netto
// osobno, wynik miesiaca linia), na dole saldo na koniec miesiaca (pole, czerwone ponizej zera)
function WykresFinansow({ miesiace }: { miesiace: MiesiacFinansow[] }) {
  const etykiety = miesiace.map((x) => miesiac(x.miesiac));
  const wynikOperacyjny = miesiace.map((x) => (x.przychody !== null && x.wydatki !== null ? x.przychody - x.wydatki : null));
  return (
    <Wykres
      wysokosc={460}
      opcje={{
        tooltip: {
          trigger: 'axis',
          axisPointer: { type: 'line' },
          formatter: (p: unknown) => {
            const lista = p as { dataIndex: number }[];
            const x = miesiace[lista[0]?.dataIndex ?? 0];
            if (!x) return '';
            const i = lista[0].dataIndex;
            return [`<b>${miesiac(x.miesiac)}</b>`,
              `Przychody: ${kwota(x.przychody)}`, `Wydatki: ${kwota(x.wydatki)}`,
              `w tym płace: ${kwota(x.place)}`,
              `Wynik bez transferów: <b>${kwota(wynikOperacyjny[i])}</b>`,
              `Transfery netto: ${kwota(x.transfery)}`,
              `Saldo na koniec miesiąca: <b>${kwota(x.saldo)}</b>`].join('<br/>');
          },
        },
        legend: { top: 0, data: ['Przychody', 'Wydatki', 'Transfery netto', 'Wynik bez transferów', 'Saldo'] },
        axisPointer: { link: [{ xAxisIndex: 'all' }] },
        grid: [
          { left: 90, right: 30, top: 40, height: '50%' },
          { left: 90, right: 30, top: '68%', bottom: 30 },
        ],
        xAxis: [
          { type: 'category', data: etykiety, gridIndex: 0, axisLabel: { show: false } },
          { type: 'category', data: etykiety, gridIndex: 1 },
        ],
        yAxis: [
          { type: 'value', gridIndex: 0, name: 'Przepływy w miesiącu', nameTextStyle: { align: 'left' },
            axisLabel: { formatter: (v: number) => kwota(v) } },
          { type: 'value', gridIndex: 1, name: 'Saldo', nameTextStyle: { align: 'left' },
            axisLabel: { formatter: (v: number) => kwota(v) }, splitNumber: 3 },
        ],
        series: [
          { name: 'Przychody', type: 'bar', stack: 'przeplyw', data: miesiace.map((x) => x.przychody),
            color: '#51cf66', barMaxWidth: 26 },
          { name: 'Wydatki', type: 'bar', stack: 'przeplyw', data: miesiace.map((x) => (x.wydatki === null ? null : -x.wydatki)),
            color: '#ff8787', barMaxWidth: 26 },
          { name: 'Transfery netto', type: 'bar', data: miesiace.map((x) => x.transfery), color: '#b197fc',
            barMaxWidth: 12 },
          { name: 'Wynik bez transferów', type: 'line', data: wynikOperacyjny, color: '#fcc419', symbolSize: 6,
            lineStyle: { width: 2 }, z: 5 },
          { name: 'Saldo', type: 'line', xAxisIndex: 1, yAxisIndex: 1, data: miesiace.map((x) => x.saldo),
            areaStyle: { opacity: 0.25 }, lineStyle: { width: 2 }, symbolSize: 5 },
        ],
      }}
    />
  );
}

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
      <WykresFinansow miesiace={m} />
      {f.wygasajace.length > 0 && (
        <>
          <Title order={6}>Kontrakty wygasające w ciągu 12 miesięcy</Title>
          <Text size="xs" c="dimmed">
            Ich płace ({eur(f.wygasajace.reduce((a, x) => a + (x.Płaca_tydzien ?? 0), 0))} / tydz.) zwolnią się
            z budżetu, jeśli nie przedłużysz umów.
          </Text>
          <Table striped maw={640}>
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
    <Table striped>
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
              <Table.Td>{o.nazwa}</Table.Td>
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

function TabelaObszarow({ obszary, opis }: { obszary: ObszarSztabu[]; opis: Record<string, string[]> }) {
  return (
    <Table maw={980}>
      <Table.Thead>
        <Table.Tr>
          <Table.Th>Obszar</Table.Th><Table.Th ta="right">Sztab</Table.Th><Table.Th>Kto</Table.Th>
          <Table.Th ta="right">Mediana ligi</Table.Th><Table.Th ta="right">Najlepszy w lidze</Table.Th>
          <Table.Th ta="right">Miejsce</Table.Th><Table.Th />
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {obszary.map((o) => (
          <Table.Tr key={o.obszar}>
            <Table.Td>
              <Tooltip label={`Atrybuty: ${(opis[o.obszar] ?? []).join(', ')}`}><span>{o.obszar}</span></Tooltip>
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
  );
}

// Wybrany obszar: obecny najlepszy czlowiek pierwszej druzyny obok kandydatow z innych klubow
function Wzmocnienie({ p }: { p: PersonelDane }) {
  const pierwszaLuka = p.obszary.find((o) => o.luka)?.obszar ?? p.obszary[0]?.obszar ?? null;
  const [obszar, setObszar] = useState<string | null>(pierwszaLuka);
  const o = p.obszary.find((x) => x.obszar === obszar);
  const obecny = p.sztab.find((m) => m.uid === o?.kto_uid);
  const kandydaci = obszar ? p.kandydaci[obszar] ?? [] : [];
  return (
    <Stack gap="xs">
      <Title order={6}>Wzmocnij obszar</Title>
      <Group align="flex-end" gap="lg">
        <Select w={SZEROKOSC.szeroka} label="Obszar" allowDeselect={false} value={obszar} onChange={setObszar}
          data={p.obszary.map((x) => ({ value: x.obszar, label: `${x.obszar}${x.luka ? ' (luka)' : ''}` }))} />
        {o && (
          <Card withBorder miw={SZEROKOSC.szeroka}>
            <Text size="xs" c="dimmed">Obecnie w pierwszej drużynie</Text>
            {obecny ? (
              <Group gap="lg">
                <Text fw={600}>{obecny.nazwa}</Text>
                <Text size="sm">{obecny.stanowisko}, {obecny.wiek ?? '–'} lat</Text>
                <Text size="sm">ocena <b style={{ color: ocenaKolor(o.moja) }}>{formatuj(o.moja, 'dec1')}</b></Text>
                <Text size="sm">{eur(obecny.placa_tydzien)} / tydz.</Text>
              </Group>
            ) : <Text fw={600}>brak osoby w tym obszarze</Text>}
          </Card>
        )}
      </Group>
      {kandydaci.length ? (
        <Table striped>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Kandydat</Table.Th><Table.Th>Klub</Table.Th><Table.Th>Stanowisko</Table.Th>
              <Table.Th ta="right">Wiek</Table.Th><Table.Th ta="right">Ocena: {obszar}</Table.Th>
              <Table.Th ta="right">Różnica</Table.Th><Table.Th ta="right">Płaca / tydz.</Table.Th>
              <Table.Th ta="right">Płaca vs obecny</Table.Th><Table.Th>Kontrakt do</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {kandydaci.map((k) => {
              const ocena = obszar ? k.oceny[obszar] : null;
              const roznica = ocena !== null && ocena !== undefined ? ocena - (o?.moja ?? 0) : null;
              const placa = k.placa_tydzien !== null && obecny?.placa_tydzien !== null && obecny
                ? k.placa_tydzien - (obecny.placa_tydzien ?? 0) : null;
              return (
                <Table.Tr key={k.uid}>
                  <Table.Td>{k.nazwa}</Table.Td><Table.Td>{k.klub}</Table.Td><Table.Td>{k.stanowisko}</Table.Td>
                  <Table.Td ta="right">{k.wiek ?? '–'}</Table.Td>
                  <Table.Td ta="right"><b style={{ color: ocenaKolor(ocena) }}>{formatuj(ocena, 'dec1')}</b></Table.Td>
                  <Table.Td ta="right" style={{ color: '#69db7c' }}>{roznica === null ? '–' : `+${formatuj(roznica, 'dec1')}`}</Table.Td>
                  <Table.Td ta="right">{eur(k.placa_tydzien)}</Table.Td>
                  <Table.Td ta="right" style={{ color: placa === null ? undefined : placa > 0 ? '#ff8787' : '#69db7c' }}>
                    {placa === null ? '–' : `${placa > 0 ? '+' : ''}${eur(placa)}`}
                  </Table.Td>
                  <Table.Td>{formatuj(k.kontrakt_do, 'data')}</Table.Td>
                </Table.Tr>
              );
            })}
          </Table.Tbody>
        </Table>
      ) : <Text size="sm" c="dimmed">Nikt z innych klubów nie jest w tym obszarze lepszy od Twojego sztabu.</Text>}
    </Stack>
  );
}

type PersonelDane = NonNullable<ReturnType<typeof api.personel> extends Promise<infer T> ? T : never>;

function Personel({ wersja }: { wersja: number }) {
  const dane = useQuery({ queryKey: ['personel', wersja], queryFn: api.personel, staleTime: Infinity, retry: false });
  const [druzyna, setDruzyna] = useState('0');
  if (dane.isLoading) {
    return (
      <Group gap="sm"><Loader size="sm" /><Text size="sm">Odczyt personelu z zapisu gry (ok. 20 s, tylko za pierwszym razem)...</Text></Group>
    );
  }
  if (dane.error) return <Alert color="red">{(dane.error as Error).message}</Alert>;
  const p = dane.data;
  if (!p) return null;
  const sloty = Object.keys(p.druzyny ?? { 0: [] }).sort((a, b) => Number(a) - Number(b));
  const nazwa = (s: string) => p.nazwy_druzyn?.[s] ?? (s === '0' ? 'Pierwsza drużyna' : `Drużyna ${Number(s) + 1}`);
  const obszary = p.druzyny?.[druzyna] ?? p.obszary;
  const sztab = p.sztab.filter((m) => String(m.druzyna) === druzyna);
  return (
    <Stack gap="md">
      <SegmentedControl w="fit-content" value={druzyna} onChange={setDruzyna}
        data={sloty.map((s) => ({ value: s, label: `${nazwa(s)} (${p.sztab.filter((m) => String(m.druzyna) === s).length})` }))} />
      <Title order={6}>Sztab: {nazwa(druzyna)} na tle tej samej drużyny w klubach ligi ({p.liga_klubow} klubów)</Title>
      <Text size="xs" c="dimmed">
        Ocena obszaru: najlepsza osoba sztabu tej drużyny w danym obszarze, w skali 1-20 (średnia atrybutów obszaru);
        liga - najlepsi w tej samej drużynie każdego klubu ligi. Luka: poniżej mediany ligi.
      </Text>
      <TabelaObszarow obszary={obszary} opis={p.obszary_opis} />
      {druzyna === '0' && <Wzmocnienie p={p} />}
      <Title order={6}>Sztab: {nazwa(druzyna)} ({sztab.length} osób)</Title>
      <TabelaOsob osoby={sztab} />
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
    <Stack gap="md">
      <SegmentedControl w="fit-content" value={widok} onChange={(v) => setWidok(v as 'finanse' | 'personel')}
        data={[{ value: 'finanse', label: 'Finanse' }, { value: 'personel', label: 'Personel' }]} />
      {widok === 'finanse' ? <Finanse wersja={wersja} /> : <Personel wersja={wersja} />}
    </Stack>
  );
}
