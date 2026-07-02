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
  } else if (type === 'TRACE') {
    if (!pyodide) {
      postMessage({ type: 'ERROR', message: 'Environment is not initialized yet.' });
      return;
    }

    try {
      const traceRunner = `
import sys
import json
import math

def serialize_val(val, visited=None):
    if visited is None:
        visited = set()
    val_id = id(val)
    if val_id in visited:
        return "<circular reference>"
    if isinstance(val, float):
        if math.isnan(val):
            return "NaN"
        elif math.isinf(val):
            return "Infinity" if val > 0 else "-Infinity"
        return val
    try:
        json.dumps(val, allow_nan=False)
        return val
    except:
        visited.add(val_id)
        try:
            if isinstance(val, (set, tuple)):
                return [serialize_val(x, visited) for x in val]
            elif isinstance(val, list):
                return [serialize_val(x, visited) for x in val]
            elif isinstance(val, dict):
                return {str(k): serialize_val(v, visited) for k, v in val.items()}
            else:
                return str(val)
        finally:
            visited.remove(val_id)

def trace_code(code_string):
    trace_data = []
    step_counter = 0

    def trace_lines(frame, event, arg):
        nonlocal step_counter
        if frame.f_code.co_filename == '<string>':
            if event in ('line', 'return'):
                step_counter += 1
                if step_counter > 500:
                    raise Exception("Trace limit exceeded (max 500 steps) to prevent infinite loops.")
                
                local_vars = {}
                for k, v in frame.f_locals.items():
                    if not k.startswith('__') and k != 'trace_code' and k != 'trace_lines' and k != 'serialize_val':
                        local_vars[k] = serialize_val(v)
                
                trace_data.append({
                    "step": step_counter,
                    "line": frame.f_lineno,
                    "variables": local_vars,
                    "event": event
                })
        return trace_lines

    globals_dict = {}
    locals_dict = {}
    
    sys.settrace(trace_lines)
    try:
        exec(code_string, globals_dict, locals_dict)
    except Exception as e:
        trace_data.append({
            "step": step_counter + 1,
            "line": 0,
            "error": str(e),
            "variables": {}
        })
    finally:
        sys.settrace(None)
        
    return json.dumps(trace_data)
`;
      await pyodide.runPythonAsync(traceRunner);
      pyodide.globals.set("user_code_str", code);
      const jsonResult = await pyodide.runPythonAsync("trace_code(user_code_str)");
      postMessage({ type: 'TRACE_RESULT', content: JSON.parse(jsonResult) });
    } catch (error) {
      postMessage({ type: 'ERROR', message: error.message });
    }
  }
};
