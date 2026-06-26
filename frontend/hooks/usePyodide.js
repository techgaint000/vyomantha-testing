import { useEffect, useRef, useState, useCallback } from 'react';

export function usePyodide({ onStdout, onStderr, onReady, onFinish, onError, onTraceResult } = {}) {
  const [isReady, setIsReady] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const workerRef = useRef(null);

  // Keep latest callbacks in ref to prevent recreating initWorker on every render
  const callbacksRef = useRef({ onStdout, onStderr, onReady, onFinish, onError, onTraceResult });
  useEffect(() => {
    callbacksRef.current = { onStdout, onStderr, onReady, onFinish, onError, onTraceResult };
  }, [onStdout, onStderr, onReady, onFinish, onError, onTraceResult]);

  const isReadyRef = useRef(isReady);
  const isRunningRef = useRef(isRunning);

  useEffect(() => {
    isReadyRef.current = isReady;
  }, [isReady]);

  useEffect(() => {
    isRunningRef.current = isRunning;
  }, [isRunning]);

  const initWorker = useCallback(() => {
    setIsReady(false);
    setIsRunning(false);

    // Create a new web worker instance from public folder
    const worker = new Worker('/workers/pyodide.worker.js');
    workerRef.current = worker;

    worker.onmessage = (event) => {
      const { type, content, message } = event.data;
      const cb = callbacksRef.current;

      switch (type) {
        case 'READY':
          setIsReady(true);
          if (cb.onReady) cb.onReady();
          break;
        case 'STDOUT':
          if (cb.onStdout) cb.onStdout(content);
          break;
        case 'STDERR':
          if (cb.onStderr) cb.onStderr(content);
          break;
        case 'TRACE_RESULT':
          setIsRunning(false);
          if (cb.onTraceResult) cb.onTraceResult(content);
          break;
        case 'FINISH':
          setIsRunning(false);
          if (cb.onFinish) cb.onFinish();
          break;
        case 'ERROR':
          setIsRunning(false);
          if (cb.onError) cb.onError(message);
          break;
        default:
          break;
      }
    };

    // Trigger Pyodide loading inside the web worker
    worker.postMessage({ type: 'INIT' });
  }, []);

  useEffect(() => {
    initWorker();
    return () => {
      if (workerRef.current) {
        workerRef.current.terminate();
      }
    };
  }, [initWorker]);

  const runCode = useCallback((code) => {
    if (!isReadyRef.current || isRunningRef.current || !workerRef.current) return;
    setIsRunning(true);
    workerRef.current.postMessage({ type: 'RUN', code });
  }, []);

  const runTrace = useCallback((code) => {
    if (!isReadyRef.current || isRunningRef.current || !workerRef.current) return;
    setIsRunning(true);
    workerRef.current.postMessage({ type: 'TRACE', code });
  }, []);

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
    runTrace,
    stopCode
  };
}
