import { useEffect, useRef, useState } from "react";

/** Compteur de secondes écoulées tant que `running` est vrai ; conserve la valeur finale. */
export function useElapsed(running: boolean) {
  const [elapsed, setElapsed] = useState(0);
  const start = useRef<number | null>(null);

  useEffect(() => {
    if (!running) {
      start.current = null;
      return;
    }
    start.current = Date.now();
    setElapsed(0);
    const id = setInterval(() => {
      if (start.current) setElapsed(Math.floor((Date.now() - start.current) / 1000));
    }, 250);
    return () => clearInterval(id);
  }, [running]);

  return elapsed;
}
