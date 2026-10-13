"""
bill_api_proxy.py  —  UPPCL consumer portal relay proxy
Accepts {key, action:"consumer_relay", path, body} JSON envelope.
Render deploy: set start command to  python bill_api_proxy.py
Local run:     python bill_api_proxy.py
"""
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.request, json, os

PORT = int(os.environ.get('PORT', 8789))
SHARED_KEY  = '5c7f3575077e0650771c98dce359a163'
APP_SVC_KEY = '$3z$23$JBC7QqHzHEzJ/TzoS5qH4.Morw8ublIgfA.0byOEKrvnMyOr1K8Aj'
UPSTREAM    = 'https://consumer.uppcl.org/uppclwss'
ALLOWED     = {'/v2/api/GetDiscom', '/v2/api/getConsumerDetails', '/v2/api/viewBillDownloadPDF'}

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f'  [{args[1] if len(args)>1 else "?"}] {self.path}')

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors(); self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self._cors()
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'UPPCL bill proxy running')

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        raw    = self.rfile.read(length)
        try:
            p = json.loads(raw)
        except Exception:
            return self._json({'ok': False, 'error': 'invalid JSON'}, 400)

        if p.get('key') != SHARED_KEY:
            return self._json({'ok': False, 'error': 'unauthorized'}, 403)
        if p.get('action') != 'consumer_relay':
            return self._json({'ok': False, 'error': 'unknown_action'}, 400)
        if p.get('path') not in ALLOWED:
            return self._json({'ok': False, 'error': 'path_not_allowed'}, 400)

        body = json.dumps(p['body']).encode()
        req  = urllib.request.Request(
            UPSTREAM + p['path'], data=body,
            headers={
                'Content-Type':  'application/json',
                'Content-Length': str(len(body)),
                'Origin':        'https://consumer.uppcl.org',
                'Referer':       'https://consumer.uppcl.org/wss/pay_bill_home',
                'appServiceKey': APP_SVC_KEY,
                'User-Agent':    'Mozilla/5.0',
            }, method='POST'
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                resp_body = r.read()
                status    = r.status
        except urllib.request.HTTPError as e:
            resp_body = e.read(); status = e.code
        except Exception as ex:
            return self._json({'ok': False, 'error': str(ex)}, 502)

        try:
            resp_json = json.loads(resp_body)
        except Exception:
            return self._json({'ok': False, 'error': 'upstream non-JSON', 'raw': resp_body[:200].decode(errors='replace')}, 502)

        self._json({'ok': status == 200, 'status': status, 'response': resp_json})

    def _json(self, obj, status=200):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self._cors()
        self.send_header('Content-Type',  'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin',  '*')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')

if __name__ == '__main__':
    srv = HTTPServer(('0.0.0.0', PORT), Handler)
    print(f'Bill proxy running on port {PORT}')
    print(f'Expose with: cloudflared tunnel --url http://localhost:{PORT}')
    srv.serve_forever()
