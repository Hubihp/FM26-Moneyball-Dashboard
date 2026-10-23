import {
  Accordion,
  Alert,
  Badge,
  Button,
  FileInput,
  Group,
  Modal,
  NumberInput,
  Progress,
  Radio,
  SegmentedControl,
  Stack,
  Switch,
  Text,
  TextInput,
} from '@mantine/core';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';

import { api, wgrajZapis, type Opcje, type Stan } from '../api';

type Props = { otwarty: boolean; zamknij: () => void; stan: Stan | undefined };

const dataPliku = (s: number) => new Date(s * 1000).toLocaleString('pl-PL', { dateStyle: 'short', timeStyle: 'short' });

export default function PanelZrodla({ otwarty, zamknij, stan }: Props) {
  const klient = useQueryClient();
  const [typ, setTyp] = useState<string>('folder');
  const [folder, setFolder] = useState('');
  const [plik, setPlik] = useState<string>('najnowszy');
  const [sledz, setSledz] = useState(true);
  const [przyStarcie, setPrzyStarcie] = useState(false);
  const [opcje, setOpcje] = useState<Opcje | null>(null);
  const [plikFm, setPlikFm] = useState<File | null>(null);
  const [postep, setPostep] = useState<number | null>(null);
  const [plikiCsv, setPlikiCsv] = useState<File[]>([]);
  const [komunikat, setKomunikat] = useState<{ kolor: string; tekst: string } | null>(null);

  // Wartosci startowe z biezacej konfiguracji serwera przy kazdym otwarciu panelu
  useEffect(() => {
    if (!otwarty || !stan) return;
    setTyp(stan.zrodlo.typ === 'brak' ? 'folder' : stan.zrodlo.typ);
    setFolder(stan.zrodlo.folder ?? '');
    setPlik(stan.zrodlo.plik && stan.zrodlo.typ === 'folder' ? stan.zrodlo.plik : 'najnowszy');
    setSledz(stan.zrodlo.sledz);
    setPrzyStarcie(stan.zrodlo.wczytaj_przy_starcie);
    setOpcje(stan.zrodlo.opcje);
    setKomunikat(null);
  }, [otwarty]); // eslint-disable-line react-hooks/exhaustive-deps

  const zapisy = useQuery({
    queryKey: ['zapisy', folder],
    queryFn: () => api.zapisy(folder || null),
    enabled: otwarty && typ === 'folder',
  });
  useEffect(() => {
    if (!folder && zapisy.data?.folder) setFolder(zapisy.data.folder);
  }, [zapisy.data, folder]);

  const odswiezStan = (nowy: Stan) => {
    klient.setQueryData(['stan'], nowy);
    klient.invalidateQueries({ queryKey: ['stan'] });
  };

  const uzyj = async () => {
    setKomunikat(null);
    try {
      if (typ === 'folder') {
        odswiezStan(await api.ustawZrodlo({
          typ, folder, plik: plik === 'najnowszy' ? null : plik, sledz, wczytaj_przy_starcie: przyStarcie,
          opcje: opcje ?? undefined,
        }));
        zamknij();
      } else if (typ === 'demo') {
        odswiezStan(await api.ustawZrodlo({ typ, wczytaj_przy_starcie: przyStarcie }));
        zamknij();
      } else if (plikFm) {
        setPostep(0);
        odswiezStan(await wgrajZapis(plikFm, setPostep));
        setPostep(null);
        zamknij();
      }
    } catch (e) {
      setPostep(null);
      setKomunikat({ kolor: 'red', tekst: (e as Error).message });
    }
  };

  const naucz = async () => {
    try {
      const wynik = await api.nazwyLig(plikiCsv);
      const nazwy = Object.values(wynik.rozpoznane);
      setKomunikat(
        nazwy.length
          ? { kolor: 'teal', tekst: `Rozpoznano ${nazwy.length} lig: ${nazwy.join(', ')}. Dane zostaną przeładowane.` }
          : { kolor: 'yellow', tekst: 'Nie dopasowano żadnej ligi - czy pliki mają kolumny Klub i Liga?' },
      );
    } catch (e) {
      setKomunikat({ kolor: 'red', tekst: (e as Error).message });
    }
  };

  const zmienOpcje = <K extends keyof Opcje>(klucz: K, wartosc: Opcje[K]) => opcje && setOpcje({ ...opcje, [klucz]: wartosc });

  return (
    <Modal opened={otwarty} onClose={zamknij} size="lg"
      title={stan?.status === 'pusto' ? 'Co wczytać?' : 'Źródło danych'}>
      <Stack>
        <SegmentedControl
          value={typ}
          onChange={setTyp}
          data={[
            { value: 'folder', label: 'Folder zapisów gry' },
            { value: 'plik', label: 'Wgraj plik .fm' },
            { value: 'demo', label: 'Dane demo' },
          ]}
        />

        {typ === 'folder' && (
          <Stack gap="xs">
            <TextInput
              label="Folder zapisów FM26"
              description="Zwykle Dokumenty\Sports Interactive\Football Manager 26\games"
              value={folder}
              onChange={(e) => setFolder(e.currentTarget.value)}
            />
            {zapisy.data && zapisy.data.pliki.length === 0 && (
              <Alert color="yellow">Brak plików .fm w tym folderze. Aplikacja musi działać na komputerze z grą.</Alert>
            )}
            {zapisy.data && zapisy.data.pliki.length > 0 && (
              <Radio.Group value={plik} onChange={setPlik} label="Zapis">
                <Stack gap={4} mt={4}>
                  <Radio value="najnowszy" label="Zawsze najnowszy (śledzi zapisy gry)" />
                  {zapisy.data.pliki.slice(0, 12).map((p) => (
                    <Radio key={p.sciezka} value={p.sciezka} label={`${p.nazwa} · ${dataPliku(p.zmieniony)} · ${p.rozmiar_mb} MB`} />
                  ))}
                </Stack>
              </Radio.Group>
            )}
            <Switch
              checked={sledz}
              onChange={(e) => setSledz(e.currentTarget.checked)}
              label="Automatycznie wczytuj nowy zapis, gdy gra zapisze stan"
            />
            <Text size="xs" c="dimmed">
              Wybór z folderu jest szybszy niż wgrywanie (plik nie jest przesyłany przez przeglądarkę). Pierwszy odczyt
              dużego zapisu trwa od kilkudziesięciu sekund do kilku minut; ponowne otwarcie tego samego zapisu jest
              natychmiastowe (pamięć podręczna).
            </Text>
          </Stack>
        )}

        {typ === 'plik' && (
          <Stack gap="xs">
            <FileInput label="Plik zapisu kariery (.fm)" placeholder="Wybierz plik" accept=".fm" value={plikFm} onChange={setPlikFm} />
            {postep !== null && <Progress value={postep} animated />}
            <Text size="xs" c="dimmed">
              Jeśli aplikacja działa na komputerze z grą, szybciej będzie wybrać zapis z folderu gry.
            </Text>
          </Stack>
        )}

        {typ === 'demo' && <Text c="dimmed">Syntetyczne dane do wypróbowania aplikacji (150 zawodników na pozycję).</Text>}

        {typ !== 'demo' && opcje && (
          <Accordion variant="contained">
            <Accordion.Item value="opcje">
              <Accordion.Control>Opcje odczytu zapisu</Accordion.Control>
              <Accordion.Panel>
                <Stack gap="xs">
                  <SegmentedControl
                    value={opcje.rodzaj_statystyk}
                    onChange={(v) => zmienOpcje('rodzaj_statystyk', v as Opcje['rodzaj_statystyk'])}
                    data={[
                      { value: 'league', label: 'Statystyki ligowe' },
                      { value: 'overall', label: 'Wszystkie rozgrywki' },
                    ]}
                  />
                  <NumberInput label="Minimalna liczba minut w sezonie" min={0} step={90} value={opcje.min_minut}
                    onChange={(v) => zmienOpcje('min_minut', Number(v) || 0)} />
                  <NumberInput label="Kurs waluty zapisu → EUR" decimalScale={3} step={0.01} value={opcje.kurs_waluty}
                    description="Zapis trzyma kwoty w walucie bazowej (najpewniej GBP); 1,157 odpowiada temu, co gra pokazuje w euro."
                    onChange={(v) => zmienOpcje('kurs_waluty', Number(v) || 1)} />
                  <Switch label="Zawodnik na wszystkich naturalnych pozycjach" checked={opcje.wszystkie_naturalne_pozycje}
                    onChange={(e) => zmienOpcje('wszystkie_naturalne_pozycje', e.currentTarget.checked)} />
                  <Switch label="Tylko kluby przypisane do ligi krajowej" checked={opcje.tylko_kluby_w_lidze}
                    onChange={(e) => zmienOpcje('tylko_kluby_w_lidze', e.currentTarget.checked)} />
                  <Switch label="Wolni agenci (zawodnicy bez klubu z minutami w sezonie)" checked={opcje.wolni_agenci ?? true}
                    onChange={(e) => zmienOpcje('wolni_agenci', e.currentTarget.checked)} />
                </Stack>
              </Accordion.Panel>
            </Accordion.Item>
            <Accordion.Item value="nazwy">
              <Accordion.Control>Nazwy lig</Accordion.Control>
              <Accordion.Panel>
                <Stack gap="xs">
                  <Text size="sm" c="dimmed">
                    Zapis nie zawiera nazw lig. Nazwy i mnożniki możesz wpisać ręcznie w zakładce „Ligi” albo wgrać tu
                    stare eksporty CSV z gry (kolumny Klub i Liga) - aplikacja dopasuje kluby i zapamięta nazwy na stałe.
                  </Text>
                  <FileInput multiple accept=".csv" placeholder="Pliki CSV" value={plikiCsv} onChange={setPlikiCsv} />
                  <Button variant="light" disabled={!plikiCsv.length || stan?.status !== 'gotowe'} onClick={naucz}>
                    Rozpoznaj ligi
                  </Button>
                </Stack>
              </Accordion.Panel>
            </Accordion.Item>
          </Accordion>
        )}

        <Switch checked={przyStarcie} onChange={(e) => setPrzyStarcie(e.currentTarget.checked)}
          label="Wczytuj to źródło automatycznie przy uruchomieniu aplikacji" />

        {komunikat && <Alert color={komunikat.kolor}>{komunikat.tekst}</Alert>}

        <Group justify="space-between">
          {stan?.meta.nazwa_zapisu ? (
            <Badge variant="light" color="gray">Teraz: {stan.meta.nazwa_zapisu}</Badge>
          ) : (
            <span />
          )}
          <Group>
            <Button variant="default" onClick={zamknij}>Anuluj</Button>
            <Button onClick={uzyj} disabled={(typ === 'plik' && !plikFm) || postep !== null}>
              {typ === 'plik' ? 'Wgraj i wczytaj' : 'Wczytaj'}
            </Button>
          </Group>
        </Group>
      </Stack>
    </Modal>
  );
}
