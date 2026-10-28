import { Alert, Anchor, Badge, Button, Group, Modal, Progress, Spoiler, Stack, Text } from '@mantine/core';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { api, type SystemInfo } from '../api';
import { usePamiec } from '../pamiec';
import { wynikWczytania } from '../pamiecSerwera';

const mb = (b: number | null) => (b ? `${(b / 2 ** 20).toFixed(0)} MB` : '');

// Stan programu: wersja, aktualizacje (sprawdzane przez serwer przy starcie), tryb okna
export function useSystem() {
  return useQuery({
    queryKey: ['system'],
    queryFn: api.system,
    staleTime: 0,
    // dopoki serwer nie skonczyl sprawdzania albo trwa instalacja - odpytujemy
    refetchInterval: (q) => {
      const d = q.state.data;
      if (!d || !d.sprawdzono) return 2000;
      return d.postep && d.postep.etap !== 'blad' ? 1000 : false;
    },
  });
}

function przeniesDane(setCzeka: (v: boolean) => void) {
  void api.przeniesZPrzegladarki().then(() => setCzeka(true));
}

function PrzyciskPrzeniesienia() {
  const [czeka, setCzeka] = useState(false);
  return czeka ? (
    <Group gap="xs">
      <Text size="sm">Przeglądarka przesłała dane? Odśwież okno, żeby je zobaczyć.</Text>
      <Button size="xs" onClick={() => window.location.reload()}>Odśwież</Button>
    </Group>
  ) : (
    <Button size="xs" variant="light" onClick={() => przeniesDane(setCzeka)}>Przenieś dane z przeglądarki</Button>
  );
}

function Postep({ s }: { s: SystemInfo }) {
  const p = s.postep;
  if (!p) return null;
  if (p.etap === 'blad') return <Text size="sm" c="red">{p.komunikat}</Text>;
  return (
    <Stack gap={4} w={320}>
      <Text size="xs">{p.etap === 'pobieranie' ? `Pobieranie... ${p.proc ?? 0}%` : p.komunikat}</Text>
      <Progress value={p.proc ?? 0} animated size="sm" />
    </Stack>
  );
}

// Paski nad zawartoscia: dostepna aktualizacja i przeniesienie danych z przegladarki
export function PasekSystemu() {
  const system = useSystem();
  const klient = useQueryClient();
  const [pominieta, setPominieta] = usePamiec<string | null>('fm-pomin-wersje', null);
  const [przeniesienieZamkniete, setPrzeniesienieZamkniete] = usePamiec('fm-przenoszenie-zamkniete', false);
  const [pozniej, setPozniej] = useState(false);
  const [bladInstalacji, setBladInstalacji] = useState<string | null>(null);
  const s = system.data;

  const instaluj = async () => {
    setBladInstalacji(null);
    try {
      klient.setQueryData(['system'], await api.instalujAktualizacje());
    } catch (e) {
      setBladInstalacji((e as Error).message);
    }
  };

  return (
    <>
      {wynikWczytania.wymuszone && (
        <Alert color="teal" m="md" mb={0} title="Dane przeniesione do programu" withCloseButton>
          Przesłano {wynikWczytania.przeniesiono} wpisów (lista życzeń, filtry, wagi, układ tabel). Wróć do okna programu
          i kliknij „Odśwież”. Tę kartę przeglądarki możesz zamknąć.
        </Alert>
      )}
      {s?.okno && wynikWczytania.pustaNaSerwerze && !przeniesienieZamkniete && (
        <Alert color="blue" m="md" mb={0} withCloseButton onClose={() => setPrzeniesienieZamkniete(true)}
          title="Lista życzeń z poprzedniej wersji">
          <Stack gap="xs">
            <Text size="sm">
              Jeśli używałeś aplikacji w przeglądarce, twoja lista życzeń, filtry i układ tabel są zapisane w tej
              przeglądarce. Przycisk otworzy ją pod adresem aplikacji, a ona prześle dane do programu.
            </Text>
            <PrzyciskPrzeniesienia />
          </Stack>
        </Alert>
      )}
      {s?.dostepna && s.wersja && s.wersja !== pominieta && !pozniej && (
        <Alert color="teal" variant="light" m="md" mb={0}
          title={`Dostępna nowa wersja ${s.wersja} (masz ${s.wersja_programu})`}>
          <Stack gap="xs">
            {s.notatki && (
              <Spoiler maxHeight={60} showLabel="Pokaż zmiany" hideLabel="Zwiń">
                <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>{s.notatki}</Text>
              </Spoiler>
            )}
            {s.postep ? <Postep s={s} /> : (
              <Group gap="xs">
                {s.mozna_instalowac ? (
                  <Button size="xs" onClick={instaluj}>Zainstaluj teraz {s.rozmiar ? `(${mb(s.rozmiar)})` : ''}</Button>
                ) : (
                  <Button size="xs" component="a" href={s.strona} target="_blank">Pobierz ze strony wydania</Button>
                )}
                <Button size="xs" variant="default" onClick={() => setPozniej(true)}>Później</Button>
                <Button size="xs" variant="subtle" color="gray" onClick={() => setPominieta(s.wersja)}>
                  Pomiń tę wersję
                </Button>
              </Group>
            )}
            {s.postep?.etap === 'blad' && (
              <Button size="xs" w="fit-content" onClick={instaluj}>Spróbuj ponownie</Button>
            )}
            {bladInstalacji && <Text size="sm" c="red">{bladInstalacji}</Text>}
            <Text size="xs" c="dimmed">
              Twoje dane (lista życzeń, historia, ustawienia, nazwy lig) są w folderze %USERPROFILE%\.fm_moneyball
              i aktualizacja ich nie zmienia.
            </Text>
          </Stack>
        </Alert>
      )}
    </>
  );
}

// Wersja w naglowku + okno "O programie" (sprawdzenie aktualizacji, przeniesienie danych)
export function WersjaProgramu() {
  const system = useSystem();
  const klient = useQueryClient();
  const [otwarte, setOtwarte] = useState(false);
  const [sprawdzanie, setSprawdzanie] = useState(false);
  const s = system.data;
  if (!s) return null;
  const sprawdz = async () => {
    setSprawdzanie(true);
    try {
      klient.setQueryData(['system'], await api.sprawdzAktualizacje());
    } finally {
      setSprawdzanie(false);
    }
  };
  return (
    <>
      <Badge variant={s.dostepna ? 'filled' : 'outline'} color={s.dostepna ? 'teal' : 'gray'} style={{ cursor: 'pointer' }}
        onClick={() => setOtwarte(true)} title="O programie i aktualizacje">
        v{s.wersja_programu}{s.dostepna ? ` → ${s.wersja}` : ''}
      </Badge>
      <Modal opened={otwarte} onClose={() => setOtwarte(false)} title={<b>FM26 Moneyball {s.wersja_programu}</b>}>
        <Stack gap="sm">
          <Group gap="xs">
            <Button size="xs" variant="light" loading={sprawdzanie} onClick={sprawdz}>Sprawdź aktualizacje</Button>
            <Text size="sm">
              {!s.sprawdzono ? 'Sprawdzanie...' : s.dostepna ? `Dostępna wersja ${s.wersja}.` : 'Masz najnowszą wersję.'}
            </Text>
          </Group>
          <Anchor size="sm" href={s.strona} target="_blank">Wszystkie wydania i opisy zmian</Anchor>
          {s.okno && (
            <Stack gap={4}>
              <Text size="sm" fw={600}>Dane z przeglądarki</Text>
              <Text size="xs" c="dimmed">
                Przenosi listę życzeń, filtry, wagi i układ tabel z przeglądarki, w której używałeś aplikacji wcześniej
                (zastępuje nimi obecne).
              </Text>
              <PrzyciskPrzeniesienia />
            </Stack>
          )}
          <Text size="xs" c="dimmed">
            Dane programu: %USERPROFILE%\.fm_moneyball (lista życzeń i ustawienia: pamiec.json, historia zawodników,
            nazwy lig i krajów, dziennik w folderze logi). Aktualizacje i odinstalowanie ich nie usuwają.
          </Text>
        </Stack>
      </Modal>
    </>
  );
}
