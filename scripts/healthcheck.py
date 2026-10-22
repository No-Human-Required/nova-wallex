"""Kubernetes Exec probe: checks database, research worker and engine heartbeat."""
import os
import urllib.request

if __name__=='__main__':
    with urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8080')+'/readyz',timeout=4) as response:
        if response.status!=200:raise SystemExit(1)
