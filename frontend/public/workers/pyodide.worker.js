// Background Worker for Pyodide Execution
importScripts('https://cdn.jsdelivr.net/pyodide/v0.26.1/full/pyodide.js');

let pyodide = null;

async function initPyodide() {
  if (pyodide) return;
  try {
    pyodide = await loadPyodide({
      indexURL: 'https://cdn.jsdelivr.net/pyodide/v0.26.1/full/',
      stdout: (text) => {
        postMessage({ type: 'STDOUT', content: text + '\n' });
      },
      stderr: (text) => {
        postMessage({ type: 'STDERR', content: text + '\n' });
      }
    });
    
    postMessage({ type: 'READY' });
  } catch (error) {
    postMessage({ type: 'ERROR', message: 'Failed to load Pyodide: ' + error.message });
  }
}

self.onmessage = async function (event) {
  const { type, code } = event.data;

  if (type === 'INIT') {
    await initPyodide();
  } else if (type === 'RUN') {
    if (!pyodide) {
      postMessage({ type: 'ERROR', message: 'Environment is not initialized yet.' });
      return;
    }

    try {
      // Auto load any imported packages from CDN
      await pyodide.loadPackagesFromImports(code);
      
      // Run Python script
      await pyodide.runPythonAsync(code);
      postMessage({ type: 'FINISH' });
    } catch (error) {
      postMessage({ type: 'STDERR', content: error.message + '\n' });
      postMessage({ type: 'FINISH' });
    }
  }
};
