"""Narrow Wallex REST adapter. Writes require an injected authorizer.

The CLI requires explicit source-bound activation; defaults allow only reads.
No redirects, no retry of POST/DELETE, no guessed credit-wallet endpoint.
"""
import json
import time
from decimal import Decimal
import urllib.error
import urllib.parse
import urllib.request

from starwallex.net import NoRedirect,APIError
from .contracts import client_id,normalize_open_orders,ContractError

class NotDispatched(PermissionError):
    """Local gate denied the request before opening a network connection."""

def order_body(intent):
    body={k:intent[k] for k in ('symbol','type','side','price','quantity','client_id')}
    if body['type']=='STOP_LIMIT':
        if body['side']!='SELL' or body['symbol']!='TRXTMN':raise ContractError('Unsupported conditional order')
        body['stop_Price']=intent['stop_price']  # Official request spelling; response is stopPrice.
    elif body['type']!='LIMIT':raise ContractError('Unsupported order type')
    if body['side'] not in {'BUY','SELL'}:raise ContractError('Invalid order side')
    return body

class WallexGateway:
    def __init__(self,key,*,subaccount_id=None,write_authorizer=None,opener=None):
        self._key=key
        if subaccount_id is not None:
            import re
            if not isinstance(subaccount_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',subaccount_id):
                raise ContractError('Invalid credit account client ID')
        self.subaccount_id=subaccount_id
        self._authorizer=write_authorizer
        self._opener=opener or urllib.request.build_opener(NoRedirect)

    def _call(self,method,path,body=None):
        if method not in {'GET','POST','DELETE'}:raise PermissionError('Method not supported')
        if method!='GET' and (self._authorizer is None or self._authorizer(method,path,body) is not True):
            raise NotDispatched('Real orders are not authorized')
        payload=json.dumps(body,allow_nan=False).encode() if body is not None else None
        headers={'X-API-Key':self._key,'Accept':'application/json','Content-Type':'application/json'}
        if self.subaccount_id:headers['sub-account-client-id']=self.subaccount_id
        req=urllib.request.Request('https://api.wallex.ir'+path,method=method,data=payload,headers=headers)
        started=time.monotonic()
        try:
            with self._opener.open(req,timeout=15) as response:
                value=json.load(response,parse_float=Decimal)
                if not isinstance(value,dict):raise ContractError('Unexpected API envelope')
                value['_transport']={'http_status':response.status,'request_id':response.headers.get('x-request-id'),
                    'server_date':response.headers.get('Date'),'received_at':time.time(),
                    'latency_seconds':time.monotonic()-started,'method':method,'path':path}
                return value
        except urllib.error.HTTPError as exc:
            # Even 404 after a timed-out submit is not proof of non-execution.
            error=APIError(exc.code,'wallex adapter')
            error.transport={'http_status':exc.code,'request_id':exc.headers.get('x-request-id') if exc.headers else None,
                             'latency_seconds':time.monotonic()-started,'method':method,'path':path}
            raise error from None
        except (TimeoutError,urllib.error.URLError):
            raise APIError(0,'wallex adapter network') from None

    def submit(self,intent):
        client_id(intent['client_id'])
        body=order_body(intent)
        return self._call('POST','/v1/account/orders',body)

    def lookup(self,cid):return self._call('GET','/v1/account/orders/'+client_id(cid))

    def cancel(self,cid):return self._call('DELETE','/v1/account/orders/'+client_id(cid))

    def fees(self):return self._call('GET','/v1/account/fee')

    def accounts(self):return self._call('GET','/sub-accounts')

    def main_balances(self):
        """Documented main wallet ONLY. Not a verified credit-account balance route."""
        return self._call('GET','/v1/account/balances')

    def detailed_balances(self):return self._call('GET','/v1/account/balances-detail')

    def open_order_ids(self,*,page_size=100,max_pages=20):
        if not 1<=page_size<=100 or not 1<=max_pages<=20:raise ValueError('Invalid pagination bound')
        seen=set()
        for page in range(1,max_pages+1):
            query=urllib.parse.urlencode({'page':page,'per_page':page_size})
            ids=normalize_open_orders(self._call('GET','/v1/account/openOrders?'+query))
            if seen.intersection(ids):raise ContractError('Open-order pages overlap; snapshot is unstable')
            seen.update(ids)
            if len(ids)<page_size:return seen
        raise ContractError('Open-order pagination incomplete; do not assume account is clear')
