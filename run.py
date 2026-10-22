"""Production entry point. One worker; persisted jobs never silently auto-resume."""
import os
import uvicorn

if __name__=='__main__':
    development=os.getenv('SW_ENV')=='development'
    uvicorn.run('app.main:create_app',factory=True,
                host='127.0.0.1' if development else '0.0.0.0',
                port=int(os.getenv('PORT','8787' if development else '8080')),
                workers=1,access_log=False,proxy_headers=False,
                limit_concurrency=40,timeout_keep_alive=5)
