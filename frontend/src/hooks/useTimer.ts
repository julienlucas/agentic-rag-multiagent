import { useState, useEffect } from "react";

export function useTimer(isLoading: boolean) {
  const [elapsedTime, setElapsedTime] = useState(0);
  const [startTime, setStartTime] = useState<number | null>(null);
  const [finalTime, setFinalTime] = useState<number | null>(null);

  // Timer pour le compteur de temps
  useEffect(() => {
    let interval: NodeJS.Timeout;

    if (isLoading && startTime) {
      interval = setInterval(() => {
        setElapsedTime(Math.floor((Date.now() - startTime) / 1000));
      }, 1000);
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [isLoading, startTime]);

  // Sauvegarder le temps final quand le loading s'arrête
  useEffect(() => {
    if (!isLoading && startTime && elapsedTime > 0) {
      setFinalTime(elapsedTime);
      setStartTime(null);
    }
  }, [isLoading, startTime, elapsedTime]);

  const startTimer = () => {
    setStartTime(Date.now());
    setElapsedTime(0);
    setFinalTime(null);
  };

  const resetTimer = () => {
    setElapsedTime(0);
    setStartTime(null);
    setFinalTime(null);
  };

  return {
    elapsedTime,
    finalTime,
    startTimer,
    resetTimer,
  };
}
