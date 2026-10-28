// Gwiazdka Listy zyczen - wspolna dla tabel (Ranking, Sprzedaj drogo, Optymalizator)
export function IkonaGwiazdki({ aktywna }: { aktywna: boolean }) {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 2.5l2.9 6.1 6.6.8-4.9 4.6 1.3 6.6L12 17.3l-5.9 3.3 1.3-6.6-4.9-4.6 6.6-.8z"
        fill={aktywna ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
    </svg>
  );
}

export function PrzyciskGwiazdki({ aktywna, przelacz }: { aktywna: boolean; przelacz: () => void }) {
  const opis = aktywna ? 'Usuń z listy życzeń' : 'Dodaj do listy życzeń';
  return (
    <button type="button" className={`gwiazdka${aktywna ? ' aktywna' : ''}`} title={opis} aria-label={opis}
      aria-pressed={aktywna}
      onClick={(e) => {
        e.stopPropagation();
        przelacz();
      }}>
      <IkonaGwiazdki aktywna={aktywna} />
    </button>
  );
}
