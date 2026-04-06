import type { ScoredPlace } from '../types';

interface Props {
  place: ScoredPlace;
  rank: number;
  onSelect: () => void;
}

export default function PlaceCard({ place, rank, onSelect }: Props) {
  const stars = '★'.repeat(Math.round(place.rating));
  const half = place.rating % 1 >= 0.5 ? '½' : '';

  return (
    <div className="place-card" onClick={onSelect} role="button" tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && onSelect()}
      aria-label={`Chọn ${place.name}`}
    >
      <div className="place-rank">{rank}</div>

      <div className="place-info">
        <div className="place-name" title={place.name}>{place.name}</div>
        <div className="place-meta">
          <span className="place-rating" title={`${place.rating}/5`}>
            {stars}{half} {place.rating.toFixed(1)}
          </span>
          <span>·</span>
          <span>{place.distance_km.toFixed(1)} km</span>
          {place.cuisine_type && (
            <>
              <span>·</span>
              <span>{place.cuisine_type}</span>
            </>
          )}
          {place.open_now !== undefined && (
            <>
              <span>·</span>
              <span className={place.open_now ? 'place-open' : 'place-closed'}>
                {place.open_now ? 'Đang mở' : 'Đóng cửa'}
              </span>
            </>
          )}
        </div>
      </div>

      <button className="place-select-btn" onClick={(e) => { e.stopPropagation(); onSelect(); }}>
        Chọn
      </button>
    </div>
  );
}
