'''
搭建web骨架，并对首页/进行响应
aiohttp是python支持异步io的web框架
'''
import logging; logging.basicConfig(level=logging.INFO)
import asyncio
from aiohttp import web

async def index(request):
    return web.Response(body=b'<h1>Index!</h1>')


async def init(loop):
    app = web.Application(loop=loop)
    app.router.add_route('GET', '/', index)
    srv = await loop.create_server(app.make_handler(), '127.0.0.1', 9000)#利用asyncio的create_server创建tcp连接
    logging.info('server started at  http://127.0.0.1:9000 ')
    return srv

loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()