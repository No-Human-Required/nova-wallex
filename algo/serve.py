"""Web process: uvicorn on $PORT (default 8080)."""
import os

import uvicorn

from .main import create_app


def main():
    uvicorn.run(create_app(), host=os.getenv('HOST', '0.0.0.0'), port=int(os.getenv('PORT', '8080')),
                proxy_headers=True, forwarded_allow_ips='*', access_log=False)


if __name__ == '__main__':
    main()
