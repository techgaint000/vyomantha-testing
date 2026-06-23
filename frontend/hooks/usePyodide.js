import { useEffect, useRef, useState, useCallback } from 'react';

export function usePyodide({ onStdout, onStderr, onReady, onFinish, onError } = {}) {
  const [isReady, setIsReady] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const workerRef = useRef(null);

  const initWorker = useCallback(() => {
    setIsReady(false);
    setIsRunning(false);

    // Create a new web worker instance from public folder
    const worker = new Worker('/workers/pyodide.worker.js');
    workerRef.current = worker;

    worker.onmessage = (event) => {
      const { type, content, message } = event.data;

      switch (type) {
        case 'READY':
          setIsReady(true);
          if (onReady) onReady();
          break;
        case 'STDOUT':
          if (onStdout) onStdout(content);
          break;
        case 'STDERR':
          if (onStderr) onStderr(content);
          break;
        case 'FINISH':
          setIsRunning(false);
          if (onFinish) onFinish();
          break;
        case 'ERROR':
          setIsRunning(false);
          if (onError) onError(message);
          break;
        default:
          break;
      }
    };

    // Trigger Pyodide loading inside the web worker
    worker.postMessage({ type: 'INIT' });
  }, [onStdout, onStderr, onReady, onFinish, onError]);

  useEffect(() => {
    initWorker();
    return () => {
      if (workerRef.current) {
        workerRef.current.terminate();
      }
    };
  }, [initWorker]);

  const runCode = useCallback((code) => {
    if (!isReady || isRunning || !workerRef.current) return;
    setIsRunning(true);
    workerRef.current.postMessage({ type: 'RUN', code });
  }, [isReady, isRunning]);

  const stopCode = useCallback(() => {
    if (workerRef.current) {
      workerRef.current.terminate();
      setIsRunning(false);
      setIsReady(false);
      // Relaunch a fresh worker immediately to handle future run commands
      initWorker();
    }
  }, [initWorker]);

  return {
    isReady,
    isRunning,
    runCode,
    stopCode
  };
}
