import logging;logging.basicConfig(level=logging.INFO)

import asyncio,os,json,time
from datetime import datetime

from aiohttp import web
from jinja2 import Environment,FileSystemLoader

import day3_orm
from day5_web_frame import add_routes,add_static



# 初始化Jinja2模板，这里值得注意是设置文件路径的path参数
def init_jinja2(app,**kw):#eg:kw:filters=dict(datetime=datetime_filter),path=r"E:\learningpython\web_app\templates
    logging.info('init jinja2...')
    '''
    block_start_string 块开始标记符，缺省是 '{%'. 
    block_end_string 块结束标记符，缺省是 '%}'. 
    variable_start_string 变量开始标记符，缺省是 '{{'. 
    variable_start_string 变量结束标记符，缺省是 '{{'. 
    comment_start_string 注释开始标记符，缺省是 '{#'. 
    comment_end_string 注释结束标记符，缺省是 '#}'
    '''
    options = dict(
        autoescape=kw.get('autoescape', True),#autoescape表示是否自动转义.这里设置默认需要转义

        block_start_string=kw.get('block_start_string', '{%'),
        block_end_string=kw.get('block_end_string', '%}'),
        variable_start_string=kw.get('variable_start_string', '{{'),
        variable_end_string=kw.get('variable_end_string', '}}'),
        auto_reload=kw.get('auto_reload', True)#自动加载
    )
    path = kw.get('path', None)
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
        logging.info('set jinja2 template path: %s' % path)
    logging.info('传递path')
    env = Environment(loader=FileSystemLoader(path), **options)#jinja2-Environment-FileSystemLoader：文件系统加载器
    filters = kw.get('filters', None)
    if filters is not None:#filters=dict(datetime=datetime_filter)
        for name, f in filters.items():
            env.filters[name] = f#env.filters[datetime]=datetimme_filter
    app['__templating__'] = env




'''
这里引入aiohttp框架的web.Application()中的middleware参数。 
middleware是一种拦截器，一个URL在被某个函数处理前，可以经过一系列的middleware的处理。
一个middleware可以改变URL的输入、输出，甚至可以决定不继续处理而直接返回。
middleware的用处就在于把通用的功能从每个URL处理函数中拿出来，集中放到一个地方。 
在我看来，middleware的感觉有点像装饰器，这与上面编写的RequestHandler有点类似。 
有官方文档可以知道，当创建web.appliction的时候，可以设置middleware参数，
而middleware的设置是通过创建一些middleware factory(协程函数)。
这些middleware factory接受一个app实例，一个handler两个参数，并返回一个新的handler。
'''

#编写一个记录url日志的middleware factory
async def logger_factory(app,handler):
    async def logger_middleware(request):
        logging.info('Request:%s%s'%(request.method,request.path))
        logging.info('Request:%s' % request)
        return await handler(request)
    return logger_middleware

#编写返回response对象的middleware factory
async def response_factory(app,handler):
    async def response_middleware(request):
        logging.info('Response handler...')
        r=await handler(request)
        if isinstance(r,web.StreamResponse):
            return r
        if isinstance(r,bytes):
            resp = web.Response(body=r)
            resp.content_type = 'application/octet-stream'
            return resp
        if isinstance(r, str):
            if r.startswith('redirect:'):  # 重定向
                return web.HTTPFound(r[9:])  # 转入别的网站
            resp = web.Response(body=r.encode('utf-8'))
            resp.content_type = 'text/html;charset=utf-8'
            return resp
        if isinstance(r,dict):
            template = r.get('__template__')
            if template is None:  # 序列化JSON那章，传递数据
                resp = web.Response(body=json.dumps(r, ensure_ascii=False, default=lambda o: o.__dict__).encode('utf-8'))  # https://docs.python.org/2/library/json.html#basic-usage
                return resp
            else:  # jinja2模板
                resp = web.Response(body=app['__templating__'].get_template(template).render(**r).encode('utf-8'))
                resp.content_type = 'text/html;charset=utf-8'
                return resp
        if isinstance(r, int) and r >= 100 and r < 600:
            return web.Response(r)
        if isinstance(r, tuple) and len(r) == 2:
            t, m = r
            if isinstance(t, int) and t >= 100 and t < 600:
                return web.Response(t, str(m))
        # default，错误
        resp = web.Response(body=str(r).encode('utf-8'))
        resp.content_type = 'text/plain;charset=utf-8'
        return resp
    return response_middleware


def datetime_filter(t):
    delta = int(time.time() - t)
    if delta < 60:
        return u'1分钟前'
    if delta < 3600:
        return u'%s分钟前' % (delta // 60)
    if delta < 86400:
        return u'%s小时前' % (delta // 3600)
    if delta < 604800:
        return u'%s天前' % (delta // 86400)
    dt = datetime.fromtimestamp(t)
    return u'%s年%s月%s日' % (dt.year, dt.month, dt.day)



async def init(loop):
    await day3_orm.create_pool(loop=loop, host='127.0.0.1', port=3306, user='www-data', password='www-data', db='awesome')
    app=web.Application(loop=loop,middlewares=[logger_factory,response_factory])
    init_jinja2(app,filters=dict(datetime=datetime_filter),path=r"D:\PycharmProjects\First-python3-webapp\www\templates")#初始化jinja2模板，也就是提供模板路径。将文件加载器值赋给app['__templating__'] = env。
    add_routes(app,'day7_handlers')
    add_static(app)
    srv=await loop.create_server(app.make_handler(),'127.0.0.1',9005)
    logging.info('Server started at http://127.0.0.1:9005...')
    return srv


loop=asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()