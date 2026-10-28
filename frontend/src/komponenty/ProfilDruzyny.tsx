import { Alert, Badge, Card, Group, Loader, SimpleGrid, Stack, Table, Text, Title } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';

import { api, type MetrykaProfilu, type ProfilDruzyny as Profil, type ZmianaOceny, type ZmianaScore } from '../api';
import { formatuj } from '../format';
import type { Ustawienia } from './PanelBoczny';
import Wykres from './Wykres';

type Props = {
  wersja: number;
  wagi: Record<string, Record<string, number>>;
  ustawienia: Ustawienia;
  otworz: (pozycja: string, id: string) => void;
};

// Kolor miejsca w lidze (jak w analizach Gradient): czolowka niebieska, srodek zolty, koncowka czerwona
function kolorMiejsca(miejsce: number, n: number) {
  const t = n > 1 ? (miejsce - 1) / (n - 1) : 0;
  return t <= 0.12 ? 'blue' : t <= 0.3 ? 'teal' : t <= 0.5 ? 'green' : t <= 0.7 ? 'yellow' : t <= 0.87 ? 'orange' : 'red';
}

function liczba(x: number, format: string) {
  if (format === 'dec3') return x.toFixed(3).replace('.', ',');
  if (format === 'zmiana2') return `${x > 0 ? '+' : ''}${x.toFixed(2).replace('.', ',')}`;
  if (format === 'dec1') return x.toFixed(1).replace('.', ',');
  return formatuj(x, format as never);
}

const Miejsce = ({ m, n }: { m: number; n: number }) => (
  <Badge color={kolorMiejsca(m, n)} variant="filled" w={52}>{m}.</Badge>
);

function Sekcja({ nazwa, metryki }: { nazwa: string; metryki: MetrykaProfilu[] }) {
  return (
    <Card withBorder padding="sm">
      <Title order={5} mb="xs">{nazwa}</Title>
      <Table fz="sm" verticalSpacing={6}>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Wskaźnik</Table.Th><Table.Th ta="right">Twoja drużyna</Table.Th>
            <Table.Th ta="right">Średnia ligi</Table.Th><Table.Th ta="center">Miejsce</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {metryki.map((m) => (
            <Table.Tr key={m.nazwa}>
              <Table.Td>
                <Text size="sm">{m.nazwa}</Text>
                {m.opis && <Text size="xs" c="dimmed">{m.opis}</Text>}
              </Table.Td>
              <Table.Td ta="right"><Text size="sm" fw={700}>{liczba(m.wartosc, m.format)}</Text></Table.Td>
              <Table.Td ta="right" c="dimmed">{liczba(m.srednia, m.format)}</Table.Td>
              <Table.Td ta="center"><Miejsce m={m.miejsce} n={m.n} /></Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Card>
  );
}

// Rozklad wszystkich klubow na osi, moja druzyna wyrozniona (jak "Team physical overview")
function Rozklad({ m }: { m: MetrykaProfilu }) {
  return (
    <div>
      <Group justify="space-between" gap={4}>
        <Text size="sm" fw={600}>{m.nazwa}</Text>
        <Text size="sm"><b>{liczba(m.wartosc, m.format)}</b> · {m.miejsce}. z {m.n}</Text>
      </Group>
      <Wykres wysokosc={56} opcje={{
        grid: { left: 8, right: 8, top: 8, bottom: 8 },
        xAxis: { type: 'value', scale: true, show: false },
        yAxis: { type: 'category', data: [''], show: false },
        tooltip: { trigger: 'item', formatter: (p: unknown) => {
          const d = (p as { data: { klub: string; value: [number, string] } }).data;
          return `${d.klub}: ${liczba(d.value[0], m.format)}`;
        } },
        series: [{
          type: 'scatter',
          data: m.rozklad.map((r) => ({ value: [r.wartosc, ''], klub: r.klub,
            symbolSize: r.moj ? 18 : 10, itemStyle: { color: r.moj ? '#fd7e14' : 'rgba(180,180,180,0.55)' } })),
        }],
      }} />
    </div>
  );
}

function TabelaZmian({ tytul, wiersze, otworz }: {
  tytul: string; wiersze: ZmianaScore[]; otworz: Props['otworz'];
}) {
  return (
    <Card withBorder padding="sm">
      <Title order={6} mb={4}>{tytul}</Title>
      {wiersze.length === 0 ? <Text size="sm" c="dimmed">Brak.</Text> : (
        <Table fz="sm">
          <Table.Tbody>
            {wiersze.map((w) => (
              <Table.Tr key={w.ID} style={{ cursor: 'pointer' }} onClick={() => otworz(w.pozycja, w.ID)}>
                <Table.Td><Text size="sm" fw={600}>{w.Piłkarz}</Text><Text size="xs" c="dimmed">{w.pozycja}</Text></Table.Td>
                <Table.Td ta="right" c="dimmed">{formatuj(w['SCORE wtedy'], 'score')} → {formatuj(w.SCORE, 'score')}</Table.Td>
                <Table.Td ta="right" fw={700} c={w['Δ SCORE'] < 0 ? 'red' : 'teal'}>{formatuj(w['Δ SCORE'], 'zmiana')}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
    </Card>
  );
}

function TabelaOcen({ tytul, wiersze }: { tytul: string; wiersze: ZmianaOceny[] }) {
  return (
    <Card withBorder padding="sm">
      <Title order={6} mb={4}>{tytul}</Title>
      {wiersze.length === 0 ? <Text size="sm" c="dimmed">Brak.</Text> : (
        <Table fz="sm">
          <Table.Tbody>
            {wiersze.map((w) => (
              <Table.Tr key={String(w.Piłkarz)}>
                <Table.Td fw={600}>{w.Piłkarz}</Table.Td>
                <Table.Td ta="right" c="dimmed">{w.wtedy.toFixed(2).replace('.', ',')} → {w.teraz.toFixed(2).replace('.', ',')}</Table.Td>
                <Table.Td ta="right" fw={700} c={w.zmiana < 0 ? 'red' : 'teal'}>
                  {`${w.zmiana > 0 ? '+' : ''}${w.zmiana.toFixed(2).replace('.', ',')}`}
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
    </Card>
  );
}

function Atletyzm({ a, otworz }: { a: NonNullable<Profil['atletyzm']>; otworz: Props['otworz'] }) {
  const polowa = Math.ceil(a.kluby.length / 2);
  return (
    <Stack gap="sm">
      <Group justify="space-between" align="end">
        <Title order={4}>Atletyzm składu</Title>
        {a.moj && (
          <Text size="sm">Twoja drużyna: <b>{formatuj(a.moj.wynik, 'dec1')}</b> · {a.moj.miejsce}. z {a.kluby.length}</Text>
        )}
      </Group>
      <Text size="xs" c="dimmed">
        Wynik 0–100 względem tej samej pozycji w lidze (50 = średnia): dystans i sprinty na 90 minut zamienione na
        odchylenie od średniej pozycji, a potem na percentyl. Liczą się zawodnicy z co najmniej {formatuj(a.prog_minut, 'int')} minutami
        w lidze dla danego klubu (25% minut możliwych), wynik drużyny to średnia ważona minutami. Mierzy faktyczną pracę
        w meczach, więc zależy też od roli zawodnika w taktyce.
      </Text>
      <SimpleGrid cols={{ base: 1, xl: 2 }}>
        <Card withBorder padding="sm">
          <Table fz="sm" verticalSpacing={4} highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Zawodnik</Table.Th><Table.Th ta="right">Minuty</Table.Th>
                <Table.Th ta="right">Dystans / 90</Table.Th><Table.Th ta="right">Sprinty / 90</Table.Th>
                <Table.Th ta="right">Atletyzm</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {a.zawodnicy.map((z) => (
                <Table.Tr key={`${z.Piłkarz}|${z.ID}`} style={{ cursor: z.ID && z.Pula ? 'pointer' : undefined }}
                  onClick={() => z.ID && z.Pula && otworz(z.Pula, z.ID)}>
                  <Table.Td><Text size="sm" fw={600}>{z.Piłkarz}</Text><Text size="xs" c="dimmed">{z.Pula}</Text></Table.Td>
                  <Table.Td ta="right">{formatuj(z.Minuty, 'int')}</Table.Td>
                  <Table.Td ta="right">{z['Dystans (km)/90'] !== undefined ? `${z['Dystans (km)/90'].toFixed(1).replace('.', ',')} km` : '–'}</Table.Td>
                  <Table.Td ta="right">{z['Sprinty/90'] !== undefined ? z['Sprinty/90'].toFixed(1).replace('.', ',') : '–'}</Table.Td>
                  <Table.Td ta="right">
                    <Badge variant="filled" w={56} color={z.Atletyzm >= 70 ? 'teal' : z.Atletyzm >= 40 ? 'yellow' : 'orange'}>
                      {formatuj(z.Atletyzm, 'dec1')}
                    </Badge>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Card>
        <Card withBorder padding="sm">
          <Title order={6} mb={4}>Ranking atletyzmu ligi</Title>
          <SimpleGrid cols={2} spacing="xs">
            {[a.kluby.slice(0, polowa), a.kluby.slice(polowa)].map((kolumna, i) => (
              <Stack key={i} gap={2}>
                {kolumna.map((k) => (
                  <Group key={k.miejsce} justify="space-between" px={6} py={2} wrap="nowrap"
                    style={k.moj ? { background: 'rgba(253,126,20,0.18)', borderRadius: 4 } : undefined}>
                    <Text size="sm" truncate>{k.miejsce}. {k.klub}</Text>
                    <Text size="sm" fw={700}>{formatuj(k.wynik, 'dec1')}</Text>
                  </Group>
                ))}
              </Stack>
            ))}
          </SimpleGrid>
        </Card>
      </SimpleGrid>
    </Stack>
  );
}

// Profil mojej druzyny na tle calej ligi (w stylu analiz Gradient Sports)
export default function ProfilDruzyny({ wersja, wagi, ustawienia, otworz }: Props) {
  const profil = useQuery({
    queryKey: ['profil-druzyny', wersja, wagi, ustawienia.k_baza, ustawienia.ignoruj_mnoznik],
    queryFn: () => api.profilDruzyny({ wagi, ignoruj_mnoznik: ustawienia.ignoruj_mnoznik, k_baza: ustawienia.k_baza }),
  });
  if (profil.isLoading) return <Loader m="md" />;
  if (profil.error) return <Alert m="md" color="red">{(profil.error as Error).message}</Alert>;
  const p = profil.data;
  if (!p) return null;
  const fizyczne = p.sekcje.find((s) => s.nazwa === 'Fizycznie');
  const t = p.tabela;

  return (
    <Stack p="md" gap="md">
      <Group justify="space-between" align="end">
        <div>
          <Title order={3}>{p.klub}</Title>
          <Text size="sm" c="dimmed">
            {p.liga} · na tle {p.kluby} klubów ligi · {p.mecze ?? '–'} meczów · wartości na mecz, chyba że opisano inaczej
          </Text>
        </div>
        {t && (
          <Group gap="xs">
            <Badge size="lg" variant="filled" color={kolorMiejsca(t.pozycja, p.kluby)}>{t.pozycja}. miejsce</Badge>
            <Badge size="lg" variant="light">{t.punkty} pkt</Badge>
            <Badge size="lg" variant="light" color="gray">{t.wygrane}-{t.remisy}-{t.porazki}</Badge>
            <Badge size="lg" variant="light" color="gray">bramki {t.gole}:{t.stracone}</Badge>
          </Group>
        )}
      </Group>
      {!p.z_zapisu && (
        <Alert color="yellow" variant="light">
          Dane nie pochodzą z zapisu gry - statystyki drużyn są przybliżone z danych zawodników, a części wskaźników brak.
        </Alert>
      )}
      {p.podsumowanie.mala_proba && (
        <Alert color="orange" variant="light">Mała próba (mniej niż 10 meczów) - miejsca w lidze mogą się jeszcze mocno zmienić.</Alert>
      )}

      <SimpleGrid cols={{ base: 1, md: 2 }}>
        <Card withBorder padding="sm">
          <Title order={5} c="teal" mb={4}>Mocne strony</Title>
          {p.podsumowanie.mocne.length ? p.podsumowanie.mocne.map((m) => (
            <Text key={m.nazwa} size="sm">{m.nazwa} - <b>{m.miejsce}. z {m.n}</b></Text>
          )) : <Text size="sm" c="dimmed">Brak wskaźników w czołowej ćwiartce ligi.</Text>}
        </Card>
        <Card withBorder padding="sm">
          <Title order={5} c="orange" mb={4}>Słabe strony</Title>
          {p.podsumowanie.slabe.length ? p.podsumowanie.slabe.map((m) => (
            <Text key={m.nazwa} size="sm">{m.nazwa} - <b>{m.miejsce}. z {m.n}</b></Text>
          )) : <Text size="sm" c="dimmed">Brak wskaźników w ostatniej ćwiartce ligi.</Text>}
        </Card>
      </SimpleGrid>

      <SimpleGrid cols={{ base: 1, xl: 2 }}>
        {p.sekcje.filter((s) => s.nazwa !== 'Fizycznie').map((s) => <Sekcja key={s.nazwa} nazwa={s.nazwa} metryki={s.metryki} />)}
        {fizyczne && (
          <Card withBorder padding="sm">
            <Title order={5} mb="xs">Fizycznie</Title>
            <Stack gap="sm">
              {fizyczne.metryki.map((m) => <Rozklad key={m.nazwa} m={m} />)}
              <Text size="xs" c="dimmed">
                Pomarańczowa kropka - twoja drużyna, szare - pozostałe kluby (prawo = więcej). Dystans sam nie przesądza
                o wynikach: drużyna częściej przy piłce zwykle biega mniej.
              </Text>
            </Stack>
          </Card>
        )}
      </SimpleGrid>

      {p.atletyzm ? <Atletyzm a={p.atletyzm} otworz={otworz} /> : (
        <Alert color="gray">Atletyzm wymaga danych o dystansie i sprintach - są tylko w zapisie gry.</Alert>
      )}

      <Stack gap="sm">
        <Title order={4}>Największe zmiany względem poprzedniego sezonu</Title>
        {!p.zmiany.historia ? (
          <Alert color="gray" variant="light">
            Potrzebna migawka z poprzedniego sezonu - powstaje automatycznie przy wczytywaniu zapisów tej kariery
            (historia w ~/.fm_moneyball/historia).
          </Alert>
        ) : (
          <>
            <Text size="xs" c="dimmed">
              Względem migawki z {formatuj(p.zmiany.data_porownania, 'data')}; tylko zawodnicy z co najmniej {p.zmiany.min_minut}{' '}
              minutami w obu sezonach. Spadki i wzrosty obok siebie - sama lista spadków przesadnie pokazuje kryzys.
            </Text>
            <SimpleGrid cols={{ base: 1, md: 2 }}>
              <TabelaZmian tytul="Największe spadki SCORE" wiersze={p.zmiany.spadki} otworz={otworz} />
              <TabelaZmian tytul="Największe wzrosty SCORE" wiersze={p.zmiany.wzrosty} otworz={otworz} />
              <TabelaOcen tytul="Największe spadki średniej oceny" wiersze={p.zmiany.oceny_spadki} />
              <TabelaOcen tytul="Największe wzrosty średniej oceny" wiersze={p.zmiany.oceny_wzrosty} />
            </SimpleGrid>
          </>
        )}
      </Stack>
    </Stack>
  );
}
