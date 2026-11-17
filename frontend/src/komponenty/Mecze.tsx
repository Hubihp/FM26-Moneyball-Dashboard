import { Alert, Badge, Card, Group, Loader, SegmentedControl, Select, SimpleGrid, Stack, Table, Text, Title, Tooltip } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';
import { useMemo, useState } from 'react';

import { api, type Mecz, type PodsumowanieMeczow } from '../api';
import { eur, formatuj, kolorWyniku } from '../format';
import { useMenuZawodnika } from './MenuZawodnika';
import type { Ustawienia } from './PanelBoczny';
import Wykres from './Wykres';

type Props = {
  wersja: number;
  ustawienia: Ustawienia;
  otworz: (pozycja: string, id: string) => void;
};

const KOLOR_WYNIKU: Record<string, string> = { W: 'teal', R: 'gray', P: 'red' };
const OKNO_SREDNIEJ = 5;

function litera(m: Mecz) {
  if (!m.rozegrany || m.gole === null || m.gole_rywala === null) return null;
  return m.gole > m.gole_rywala ? 'W' : m.gole === m.gole_rywala ? 'R' : 'P';
}

const dec = (x: number | null | undefined, miejsca = 2) =>
  x === null || x === undefined ? '–' : x.toFixed(miejsca).replace('.', ',');

function Forma({ forma }: { forma: string }) {
  return (
    <Group gap={3}>
      {forma.split('').map((l, i) => (
        <Badge key={i} size="sm" radius="sm" variant="filled" color={KOLOR_WYNIKU[l]} w={22} p={0}>{l}</Badge>
      ))}
    </Group>
  );
}

function Liczba({ etykieta, wartosc, opis }: { etykieta: string; wartosc: string; opis?: string }) {
  const tresc = (
    <Stack gap={0}>
      <Text size="xs" c="dimmed">{etykieta}</Text>
      <Text size="lg" fw={700}>{wartosc}</Text>
    </Stack>
  );
  return opis ? <Tooltip multiline w={300} label={opis}><div>{tresc}</div></Tooltip> : tresc;
}

function Podsumowanie({ p }: { p: PodsumowanieMeczow }) {
  const roznica = p.xpkt === null ? null : p.punkty_z_xg - p.xpkt;
  return (
    <SimpleGrid cols={{ base: 2, md: 6 }}>
      <Liczba etykieta="Bilans (W-R-P)" wartosc={`${p.wygrane}-${p.remisy}-${p.porazki}`} />
      <Liczba etykieta="Gole" wartosc={`${p.gole}:${p.stracone}`} />
      <Liczba etykieta="xG za : przeciw" wartosc={`${dec(p.xg, 1)} : ${dec(p.xg_rywala, 1)}`}
        opis={`Suma z ${p.mecze_z_xg} meczów, dla których gra zachowała statystyki (gole w tych meczach ${p.gole_z_xg}:${p.stracone_z_xg}).`} />
      <Liczba etykieta="xG na mecz" wartosc={`${dec(p.xg_mecz)} : ${dec(p.xg_rywala_mecz)}`} />
      <Liczba etykieta="Punkty / oczekiwane" wartosc={`${p.punkty_z_xg} / ${dec(p.xpkt, 1)}`}
        opis={'Punkty oczekiwane (xPts): z xG obu drużyn liczona jest szansa wygranej, remisu i porażki (rozkład Poissona). '
          + `Więcej punktów niż oczekiwane (${roznica === null ? '–' : (roznica > 0 ? '+' : '') + dec(roznica, 1)}) `
          + 'zwykle oznacza szczęście lub świetną skuteczność, mniej - pecha.'} />
      <Stack gap={2}>
        <Text size="xs" c="dimmed">Forma (ostatnie 5)</Text>
        <Forma forma={p.forma} />
      </Stack>
    </SimpleGrid>
  );
}

const kluczMeczu = (m: Mecz) => `${m.data}|${m.rywal_uid}`;

function TabelaMeczow({ mecze, naRywala, wybrany, naWskazanie }: {
  mecze: Mecz[]; naRywala?: (uid: string) => void;
  wybrany?: string | null; naWskazanie?: (klucz: string | null) => void;
}) {
  return (
    <Table striped highlightOnHover withTableBorder fz="xs">
      <Table.Thead>
        <Table.Tr>
          <Table.Th>Data</Table.Th>
          <Table.Th>Rozgrywki</Table.Th>
          <Table.Th>Rywal</Table.Th>
          <Table.Th ta="center">Wynik</Table.Th>
          <Table.Th ta="right">xG</Table.Th>
          <Table.Th ta="right">xG rywala</Table.Th>
          <Table.Th ta="right">Strzały (celne)</Table.Th>
          <Table.Th ta="right">Posiadanie</Table.Th>
          <Table.Th ta="right">xPts</Table.Th>
          <Table.Th>Ocena</Table.Th>
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {[...mecze].reverse().map((m) => {
          const l = litera(m);
          return (
            <Table.Tr key={kluczMeczu(m)} data-mecz={kluczMeczu(m)}
              style={{ cursor: naRywala ? 'pointer' : undefined,
                background: wybrany === kluczMeczu(m) ? 'var(--mantine-color-teal-light)' : undefined }}
              onMouseEnter={naWskazanie ? () => naWskazanie(kluczMeczu(m)) : undefined}
              onMouseLeave={naWskazanie ? () => naWskazanie(null) : undefined}
              onClick={naRywala ? () => naRywala(m.rywal_uid) : undefined}>
              <Table.Td>{formatuj(m.data, 'data')}</Table.Td>
              <Table.Td>{m.rozgrywki}</Table.Td>
              <Table.Td>{m.u_siebie ? '' : '@ '}{m.rywal}</Table.Td>
              <Table.Td ta="center">
                {l ? <Badge size="sm" radius="sm" color={KOLOR_WYNIKU[l]} variant="light">{m.gole}:{m.gole_rywala}</Badge> : '–'}
              </Table.Td>
              <Table.Td ta="right">{dec(m.xg)}</Table.Td>
              <Table.Td ta="right">{dec(m.xg_rywala)}</Table.Td>
              <Table.Td ta="right">
                {m.strzaly ?? '–'} ({m.celne ?? '–'}) : {m.strzaly_rywala ?? '–'} ({m.celne_rywala ?? '–'})
              </Table.Td>
              <Table.Td ta="right">{m.posiadanie === null ? '–' : `${m.posiadanie}%`}</Table.Td>
              <Table.Td ta="right">{dec(m.xpkt)}</Table.Td>
              <Table.Td>
                {m.ocena ? (
                  <Badge size="xs" variant="light" color={m.ocena.startsWith('szczęśliw') ? 'yellow' : 'grape'}>{m.ocena}</Badge>
                ) : null}
              </Table.Td>
            </Table.Tr>
          );
        })}
      </Table.Tbody>
    </Table>
  );
}

// Srednia kroczaca xG przeciw (ostatnie OKNO_SREDNIEJ meczow z xG); wskazany mecz podswietlony na wykresie,
// klikniecie punktu wskazuje mecz w tabeli
function WykresXg({ mecze, wybrany, naWybor }: { mecze: Mecz[]; wybrany: string | null; naWybor: (k: string) => void }) {
  const z = mecze.filter((m) => m.xg !== null && m.xg_rywala !== null);
  const indeks = wybrany ? z.findIndex((m) => kluczMeczu(m) === wybrany) : -1;
  const srednia = (klucz: 'xg' | 'xg_rywala') => z.map((_, i) => {
    const okno = z.slice(Math.max(0, i - OKNO_SREDNIEJ + 1), i + 1);
    return Number((okno.reduce((a, m) => a + (m[klucz] ?? 0), 0) / okno.length).toFixed(2));
  });
  if (z.length < 3) return null;
  return (
    <Wykres
      wysokosc={260}
      opcje={{
        tooltip: {
          trigger: 'axis',
          formatter: (p: unknown) => {
            const lista = p as { dataIndex: number; seriesName: string; value: number }[];
            const m = z[lista[0]?.dataIndex ?? 0];
            return [`<b>${formatuj(m.data, 'data')} ${m.u_siebie ? '' : '@ '}${m.rywal} ${m.gole}:${m.gole_rywala}</b>`,
              `xG w meczu: ${dec(m.xg)} : ${dec(m.xg_rywala)}`,
              ...lista.map((s) => `${s.seriesName}: ${dec(s.value)}`)].join('<br/>');
          },
        },
        legend: { top: 0 },
        grid: { left: 40, right: 20, top: 35, bottom: 30 },
        xAxis: { type: 'category', data: z.map((m) => formatuj(m.data, 'data')) },
        yAxis: { type: 'value', min: 0 },
        series: [
          { name: `xG przeciw (średnia z ${OKNO_SREDNIEJ})`, type: 'line', data: srednia('xg_rywala'), color: '#ff8787',
            smooth: true, emphasis: { focus: 'none', scale: 2 }, symbolSize: 6 },
        ],
      }}
      podswietl={indeks >= 0 ? indeks : null}
      naKlik={(_, i) => { if (i !== undefined && z[i]) naWybor(kluczMeczu(z[i])); }}
    />
  );
}

function RaportRywala({ uid, ustawienia, wersja, otworz }: { uid: string } & Props) {
  const menu = useMenuZawodnika();
  const raport = useQuery({
    queryKey: ['rywal', wersja, uid, ustawienia.k_baza, ustawienia.ignoruj_mnoznik],
    queryFn: () => api.rywal({ uid, ignoruj_mnoznik: ustawienia.ignoruj_mnoznik, k_baza: ustawienia.k_baza }),
  });
  if (raport.isLoading) return <Loader size="sm" />;
  if (raport.error) return <Alert color="red">{(raport.error as Error).message}</Alert>;
  const r = raport.data;
  if (!r) return null;
  const p = r.podsumowanie;
  const moje = r.moje_podsumowanie;
  const porownanie: [string, number | null, number | null, boolean][] = [
    ['xG na mecz', p.xg_mecz, moje.xg_mecz, true],
    ['xG rywali na mecz', p.xg_rywala_mecz, moje.xg_rywala_mecz, false],
    ['Gole na mecz', p.mecze ? p.gole / p.mecze : null, moje.mecze ? moje.gole / moje.mecze : null, true],
    ['Stracone na mecz', p.mecze ? p.stracone / p.mecze : null, moje.mecze ? moje.stracone / moje.mecze : null, false],
  ];
  return (
    <Stack gap="sm">
      <Group gap="lg" align="flex-end">
        <Title order={5}>{r.nazwa ?? 'Rywal'}</Title>
        {r.tabela && (
          <Text size="sm">
            {r.tabela.pozycja}. miejsce w tabeli ({r.tabela.punkty} pkt, {r.tabela.mecze} meczów, gole {r.tabela.gole}:{r.tabela.stracone})
            {r.moja_tabela ? ` · Ty: ${r.moja_tabela.pozycja}. (${r.moja_tabela.punkty} pkt)` : ''}
          </Text>
        )}
      </Group>
      <Text size="xs" c="dimmed">Ostatnie {p.mecze} meczów rywala (wszystkie rozgrywki):</Text>
      <Podsumowanie p={p} />
      <Table withTableBorder fz="xs" maw={560}>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Ostatnie {Math.min(p.mecze, moje.mecze)} meczów</Table.Th>
            <Table.Th ta="right">{r.nazwa ?? 'Rywal'}</Table.Th>
            <Table.Th ta="right">Ty</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {porownanie.map(([nazwa, a, b, wiecejLepiej]) => (
            <Table.Tr key={nazwa}>
              <Table.Td>{nazwa}</Table.Td>
              <Table.Td ta="right">{dec(a)}</Table.Td>
              <Table.Td ta="right" style={{ color: a === null || b === null || a === b ? undefined
                : (b > a) === wiecejLepiej ? '#69db7c' : '#ff8787' }}>{dec(b)}</Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>

      <Title order={6}>Kluczowi zawodnicy (najwyższy SCORE, co najmniej 900 minut)</Title>
      {r.kluczowi.length ? (
        <Table striped highlightOnHover withTableBorder fz="xs">
          <Table.Thead>
            <Table.Tr>
              <Table.Th>SCORE</Table.Th>
              <Table.Th>Piłkarz</Table.Th>
              <Table.Th>Pozycje</Table.Th>
              <Table.Th ta="right">Wiek</Table.Th>
              <Table.Th ta="right">Minuty</Table.Th>
              <Table.Th>Rola FM</Table.Th>
              <Table.Th ta="right">Wartość</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {r.kluczowi.map((z) => (
              <Table.Tr key={z.ID} style={{ cursor: 'pointer' }} onClick={() => otworz(z.pozycja_puli, z.ID)}
                onContextMenu={(e) => menu.otworzMenu(e, { id: z.ID, pozycja: z.pozycja_puli, pilkarz: z.Piłkarz,
                  wiersz: { ID: z.ID, Piłkarz: z.Piłkarz, Klub_UID: z.Klub_UID } })}>
                <Table.Td>
                  <Badge variant="filled" radius="sm" style={{ background: kolorWyniku(z.SCORE), color: '#222' }}>
                    {Math.round(z.SCORE)}
                  </Badge>
                </Table.Td>
                <Table.Td>{z.Piłkarz}</Table.Td>
                <Table.Td>{z.Pozycja ?? z.pozycja_puli}</Table.Td>
                <Table.Td ta="right">{z.Wiek ?? '–'}</Table.Td>
                <Table.Td ta="right">{z.Minuty ?? '–'}</Table.Td>
                <Table.Td>{z['Rola FM'] ? `${z['Rola FM']} (${dec(z['Ocena roli'], 1)})` : '–'}</Table.Td>
                <Table.Td ta="right">{eur(z.Wartość_Numeryczna)}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      ) : <Text size="xs" c="dimmed">Brak zawodników rywala w danych (np. liga rywala nie jest wczytana).</Text>}

      {r.z_nami.length > 0 && (
        <>
          <Title order={6}>Nasze mecze z tym rywalem</Title>
          <TabelaMeczow mecze={r.z_nami} />
        </>
      )}
      <Title order={6}>Ostatnie mecze rywala</Title>
      <TabelaMeczow mecze={r.mecze} />
      <Text size="xs" c="dimmed">
        Taktyki rywala zapis gry nie zawiera. Kluczowi zawodnicy - według SCORE z bieżących ustawień wag (kliknięcie
        otwiera kartę zawodnika).
      </Text>
    </Stack>
  );
}

export default function Mecze(props: Props) {
  const { wersja } = props;
  const dane = useQuery({ queryKey: ['mecze', wersja], queryFn: api.mecze });
  const [widok, setWidok] = useState<'analiza' | 'rywal'>('analiza');
  const [sezon, setSezon] = useState<string | null>(null);
  const [rywal, setRywal] = useState<string | null>(null);
  const [wskazany, setWskazany] = useState<string | null>(null);     // mecz wskazany w tabeli albo na wykresie
  const wybierzNaWykresie = (k: string) => {
    setWskazany(k);
    document.querySelector(`[data-mecz="${k}"]`)?.scrollIntoView({ block: 'center', behavior: 'smooth' });
  };
  const mecze = dane.data?.mecze ?? [];
  const najblizsze = dane.data?.najblizsze ?? [];
  const sezony = useMemo(() => [...new Set(mecze.map((m) => m.sezon))].sort((a, b) => b - a), [mecze]);
  const sezonWybrany = sezon ?? (sezony.length ? String(sezony[0]) : null);
  const meczeSezonu = mecze.filter((m) => sezonWybrany === 'wszystkie' || String(m.sezon) === sezonWybrany);
  const podsumowanie = useMemo(() => policzPodsumowanie(meczeSezonu), [meczeSezonu]);
  // domyslnie najblizszy rywal; inaczej - ostatni
  const rywale = [...najblizsze.map((m) => ({ m, nadchodzacy: true })),
    ...[...mecze].reverse().map((m) => ({ m, nadchodzacy: false }))];
  const opcjeRywali = rywale.filter((x, i) => rywale.findIndex((y) => y.m.rywal_uid === x.m.rywal_uid) === i)
    .slice(0, 30)
    .map(({ m, nadchodzacy }) => ({ value: m.rywal_uid,
      label: `${m.rywal} - ${nadchodzacy ? 'najbliższy mecz' : 'ostatni mecz'} ${formatuj(m.data, 'data')}${m.u_siebie ? ' (dom)' : ' (wyjazd)'}` }));
  const rywalWybrany = rywal ?? opcjeRywali[0]?.value ?? null;

  if (dane.isLoading) return <Loader m="md" />;
  if (dane.error) return <Alert m="md" color="red">{(dane.error as Error).message}</Alert>;
  if (!dane.data?.ma_dane) {
    return <Alert m="md" color="gray">Analiza meczów wymaga zapisu gry z Twoim klubem (przy CSV i danych demo jej nie ma).</Alert>;
  }
  return (
    <Stack p="md" gap="md">
      <Group justify="space-between">
        <SegmentedControl value={widok} onChange={(v) => setWidok(v as 'analiza' | 'rywal')}
          data={[{ value: 'analiza', label: 'Analiza meczów' }, { value: 'rywal', label: 'Raport o rywalu' }]} />
        {widok === 'analiza' && sezony.length > 0 && (
          <Select size="xs" w={200} value={sezonWybrany} onChange={setSezon} allowDeselect={false}
            data={[...sezony.map((s) => ({ value: String(s), label: `Sezon ${s}/${String((s + 1) % 100).padStart(2, '0')}` })),
              { value: 'wszystkie', label: 'Wszystkie mecze' }]} />
        )}
        {widok === 'rywal' && (
          <Select w={420} searchable value={rywalWybrany} onChange={setRywal} data={opcjeRywali} allowDeselect={false}
            placeholder="Wybierz rywala" />
        )}
      </Group>
      {widok === 'analiza' ? (
        <>
          <Card withBorder>
            <Podsumowanie p={podsumowanie} />
            {(podsumowanie.szczesliwe > 0 || podsumowanie.pechowe > 0) && (
              <Text size="xs" c="dimmed" mt="xs">
                Mecze wbrew xG: szczęśliwe {podsumowanie.szczesliwe}, pechowe {podsumowanie.pechowe} (wynik inny niż
                wskazuje różnica xG co najmniej {dec(dane.data.prog_szczescia, 1)}).
              </Text>
            )}
          </Card>
          <WykresXg mecze={meczeSezonu} wybrany={wskazany} naWybor={wybierzNaWykresie} />
          {najblizsze.length > 0 && (
            <Text size="sm">
              Najbliższe mecze: {najblizsze.slice(0, 5).map((m) => `${formatuj(m.data, 'data')} ${m.u_siebie ? '' : '@ '}${m.rywal}`).join(' · ')}
            </Text>
          )}
          <Text size="xs" c="dimmed">
            Najechanie na mecz w tabeli podświetla go na wykresie, kliknięcie punktu na wykresie wskazuje mecz w tabeli.
            Kliknięcie meczu w tabeli otwiera raport o rywalu. Gra zachowuje xG tylko części meczów.
          </Text>
          <TabelaMeczow mecze={meczeSezonu} naRywala={(uid) => { setRywal(uid); setWidok('rywal'); }}
            wybrany={wskazany} naWskazanie={setWskazany} />
        </>
      ) : rywalWybrany ? (
        <RaportRywala uid={rywalWybrany} {...props} />
      ) : <Text c="dimmed">Brak rywali w terminarzu.</Text>}
    </Stack>
  );
}

// Podsumowanie wybranych meczow (jak fm_moneyball/mecze.py podsumowanie)
function policzPodsumowanie(mecze: Mecz[]): PodsumowanieMeczow {
  const roz = mecze.filter((m) => m.rozegrany);
  const zXg = roz.filter((m) => m.xpkt !== null);
  const pkt = (m: Mecz) => ({ W: 3, R: 1, P: 0 }[litera(m) ?? 'P'] ?? 0);
  const suma = (l: Mecz[], f: (m: Mecz) => number) => l.reduce((a, m) => a + f(m), 0);
  return {
    mecze: roz.length, wygrane: roz.filter((m) => litera(m) === 'W').length,
    remisy: roz.filter((m) => litera(m) === 'R').length, porazki: roz.filter((m) => litera(m) === 'P').length,
    gole: suma(roz, (m) => m.gole ?? 0), stracone: suma(roz, (m) => m.gole_rywala ?? 0),
    mecze_z_xg: zXg.length, xg: zXg.length ? suma(zXg, (m) => m.xg ?? 0) : null,
    xg_rywala: zXg.length ? suma(zXg, (m) => m.xg_rywala ?? 0) : null,
    gole_z_xg: suma(zXg, (m) => m.gole ?? 0), stracone_z_xg: suma(zXg, (m) => m.gole_rywala ?? 0),
    punkty_z_xg: suma(zXg, pkt), xpkt: zXg.length ? suma(zXg, (m) => m.xpkt ?? 0) : null,
    xg_mecz: zXg.length ? suma(zXg, (m) => m.xg ?? 0) / zXg.length : null,
    xg_rywala_mecz: zXg.length ? suma(zXg, (m) => m.xg_rywala ?? 0) / zXg.length : null,
    forma: roz.slice(-5).map((m) => litera(m)).join(''),
    szczesliwe: roz.filter((m) => (m.ocena ?? '').startsWith('szczęśliw')).length,
    pechowe: roz.filter((m) => (m.ocena ?? '').startsWith('pechow')).length,
  };
}
