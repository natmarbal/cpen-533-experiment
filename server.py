import time
import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

class SimpleHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def handle_error(self, request, client_address):
        import sys
        if sys.exc_info()[0] in (BrokenPipeError, ConnectionResetError):
            pass
        else:
            super().handle_error(request, client_address)

    def do_GET(self):
        for i in range(5_000_000):
            _ = i * i
            
        try:
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            response = {'Message': 'Success'}
            self.wfile.write(json.dumps(response).encode('utf-8'))
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self):
        self.do_GET()

def run_server(port):
    server_address = ('0.0.0.0', port)
    httpd = HTTPServer(server_address, SimpleHandler)
    print(f'Start SPINNING-python server. Addr: 0.0.0.0:{port}')
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--addr', type=str, default='localhost:50051', help='Address:Port the server is listening to')
    args = parser.parse_args()
    
    if ':' in args.addr:
        host, port_str = args.addr.split(':')
        port = int(port_str)
    else:
        port = int(args.addr)
        
    run_server(port)
