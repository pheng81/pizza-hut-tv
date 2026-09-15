import requests, json
key='AlzaSyCx531c9HrtHc9RJga0CKTYjAHOb1bvfvY'
addr='3/118 Hardwick Cres, Holt ACT 2615, Australia'
try:
    r = requests.get('https://maps.googleapis.com/maps/api/geocode/json', params={'address':addr,'key':key}, timeout=10)
    print('HTTP', r.status_code)
    j = r.json()
    print('status=', j.get('status'))
    if 'error_message' in j:
        print('error_message=', j.get('error_message'))
    if j.get('status')!='OK':
        print(json.dumps(j, indent=2))
    else:
        print(json.dumps(j['results'][0]['geometry']['location'], indent=2))
except Exception as e:
    print('EXCEPTION', e)
