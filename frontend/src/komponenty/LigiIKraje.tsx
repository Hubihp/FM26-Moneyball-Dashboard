import { Button, Checkbox, Group, Stack, Text, TextInput } from '@mantine/core';
import { useState } from 'react';

type Pozycja = { nazwa: string; liczba: number };

const NA_START = 5;

// Lista pol wyboru: 5 najliczniejszych, reszta po "Pokaz wiecej"; zaznaczone zawsze widoczne
function Lista({ tytul, pozycje, wybrane, setWybrane }: {
  tytul: string;
  pozycje: Pozycja[];
  wybrane: string[];
  setWybrane: (v: string[]) => void;
}) {
  const [wiecej, setWiecej] = useState(false);
  const [szukaj, setSzukaj] = useState('');
  if (pozycje.length === 0) return null;

  const fraza = szukaj.trim().toLowerCase();
  const widoczne = wiecej
    ? pozycje.filter((p) => !fraza || p.nazwa.toLowerCase().includes(fraza))
    : [...pozycje.slice(0, NA_START), ...pozycje.slice(NA_START).filter((p) => wybrane.includes(p.nazwa))];
  const przelacz = (nazwa: string) =>
    setWybrane(wybrane.includes(nazwa) ? wybrane.filter((w) => w !== nazwa) : [...wybrane, nazwa]);

  return (
    <Stack gap={4}>
      <Group justify="space-between">
        <Text size="sm" fw={500}>{tytul}</Text>
        {wybrane.length > 0 && (
          <Button variant="subtle" size="compact-xs" onClick={() => setWybrane([])}>Wyczyść ({wybrane.length})</Button>
        )}
      </Group>
      {wiecej && pozycje.length > 10 && (
        <TextInput size="xs" placeholder={`Szukaj: ${tytul.toLowerCase()}`} value={szukaj}
          onChange={(e) => setSzukaj(e.currentTarget.value)} />
      )}
      {widoczne.map((p) => (
        <Checkbox key={p.nazwa} size="xs" checked={wybrane.includes(p.nazwa)} onChange={() => przelacz(p.nazwa)}
          label={<Text size="xs" span>{p.nazwa} <Text span size="xs" c="dimmed">({p.liczba})</Text></Text>} />
      ))}
      {pozycje.length > NA_START && (
        <Button variant="subtle" size="compact-xs" onClick={() => { setWiecej(!wiecej); setSzukaj(''); }}
          style={{ alignSelf: 'flex-start' }}>
          {wiecej ? 'Pokaż mniej' : `Pokaż więcej (${pozycje.length - NA_START})`}
        </Button>
      )}
    </Stack>
  );
}

type Props = {
  ligi: Pozycja[];
  kraje: Pozycja[];
  wybraneLigi: string[];
  wybraneKraje: string[];
  setLigi: (v: string[]) => void;
  setKraje: (v: string[]) => void;
};

// Filtr "Ligi i kraje" w panelu bocznym (zawodnik musi spelniac oba wybory, jesli sa)
export default function LigiIKraje({ ligi, kraje, wybraneLigi, wybraneKraje, setLigi, setKraje }: Props) {
  return (
    <Stack gap="xs">
      <Text fw={600} size="sm">Ligi i kraje</Text>
      <Lista tytul="Ligi" pozycje={ligi} wybrane={wybraneLigi} setWybrane={setLigi} />
      <Lista tytul="Kraje (narodowość)" pozycje={kraje} wybrane={wybraneKraje} setWybrane={setKraje} />
    </Stack>
  );
}
