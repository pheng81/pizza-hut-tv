import sys, os, traceback, time
print('DEBUG_LAUNCH: Python', sys.version, flush=True)
print('CWD=', os.getcwd(), flush=True)
print('Files in CWD (truncated):', str(os.listdir('.'))[:500], flush=True)
start = time.time()
try:
    import app  # importing defines app.app
    print('Imported app module successfully in', round(time.time()-start,3),'s', flush=True)
except Exception as e:
    print('FAILED importing app:', e, flush=True)
    traceback.print_exc()
    sys.exit(1)
print('About to invoke Flask development server explicitly via app.app.run()', flush=True)
try:
    app.app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT',5002)))
except Exception as e:
    print('FAILED running server:', e, flush=True)
    traceback.print_exc()
    sys.exit(2)
