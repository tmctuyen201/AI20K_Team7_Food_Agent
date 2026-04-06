import { useEffect } from 'react';

interface Props {
  message: string;
  type?: 'success' | 'error';
  onDone: () => void;
  duration?: number;
}

export default function Toast({ message, type = 'success', onDone, duration = 2500 }: Props) {
  useEffect(() => {
    const t = setTimeout(onDone, duration);
    return () => clearTimeout(t);
  }, [onDone, duration]);

  return (
    <div className={`toast ${type}`} role="alert">
      {type === 'success' ? '✓ ' : '✗ '}
      {message}
    </div>
  );
}
