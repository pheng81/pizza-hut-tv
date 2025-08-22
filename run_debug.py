import runpy, traceback, sys
print('== run_debug bootstrap ==')
try:
    runpy.run_module('app', run_name='__main__')
except SystemExit as e:
    print('SystemExit:', e, 'code=', e.code)
except Exception:
    traceback.print_exc()
    sys.exit(1)
