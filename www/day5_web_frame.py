
#aiohttp:是一个http框架，对web开发来说还是较底层；
#为了少写代码，从而产生了web框架，例如：django;
#day5就是学习怎么写一个web框架。web框架需要做如下几件事：
#1、编写url处理函数
#2、传入的参数需要自己从request中获取
#需要构造出Response对象
import inspect,asyncio
from day5_error_api import APIError
from aiohttp import web
from urllib import parse#注意：request 是urllib自带的内建模块。而requests是第三方模块
import functools
import logging;logging.basicConfig(level=logging.INFO)
import os


'''
#带参数的三层装饰器，用来装饰url处理函数
def get(path):
    #Define decorator @get('/path')

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = 'GET'
        wrapper.__route__ = path
        return wrapper
    return decorator

def post(path):
    #Define decorator @get('/path')
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):#对于任意函数，都可以通过类似func(*args, **kw)的形式调用它，无论它的参数是如何定义的。
            return func(*args, **kw)
        wrapper.__method__ = 'POST'
        wrapper.__route__ = path
        return wrapper
    return decorator
'''

#用偏函数实现get\post装饰器。用来装饰URL处理函数，并存储方法（GET、POST）和URL路径信息

def Handler_decorator(path,*,method):#method是命名关键字参数，传值的时候必须带着参数名传递
    def decorator(func):
        @functools.wraps(func)#更正函数签名：直接将func的__name__属性复制一份到wraps里面
        def wrapper(*args,**kw):
            return func(*args,**kw)
        wrapper.__route__ = path #存储路径信息,注意这里属性名叫route
        wrapper.__method__ = method #存储方法信息
        return wrapper
    return decorator
#注意：get/post装饰器函数有两个参数
get=functools.partial(Handler_decorator,method='GET')
post=functools.partial(Handler_decorator,method='POST')


#inspect是python内置的模块，运用inspect，创建几个函数用以获取URL处理函数与request参数之间的关系
def get_required_kw_args(fn): #收集没有默认值的命名关键字参数
    args = []
    params = inspect.signature(fn).parameters #inspect模块是用来分析模块，函数
    for name, param in params.items():
        #KEYWORD_ONLY代表命名关键字参数
        if str(param.kind) == 'KEYWORD_ONLY' and param.default == inspect.Parameter.empty:
            args.append(name)
    return tuple(args)#将没有默认值的命名关键字用tuple形式返回

def get_named_kw_args(fn):  #获取命名关键字参数
    args = []
    params = inspect.signature(fn).parameters
    for name,param in params.items():
        if str(param.kind) == 'KEYWORD_ONLY':
            args.append(name)
    return tuple(args)

def has_named_kw_arg(fn): #判断有没有命名关键字参数
    params = inspect.signature(fn).parameters
    for name,param in params.items():
        if str(param.kind) == 'KEYWORD_ONLY':
            return True

def has_var_kw_arg(fn): #判断有没有关键字参数
    params = inspect.signature(fn).parameters
    for name,param in params.items():
        if str(param.kind) == 'VAR_KEYWORD':
            return True

def has_request_arg(fn): #判断是否含有名叫'request'参数，且该参数是否为最后一个参数
    params = inspect.signature(fn).parameters
    sig = inspect.signature(fn)
    found = False
    for name,param in params.items():
        if name == 'request':
            found = True
            continue #跳出当前循环，进入下一个循环
        #如果request参数是最后一个参数，那么执行continue后就直接跳出了整个循环，就不会执行下面的if语句了。
        #如果request不是最后一个参数，执行下面的if语句：
        if found and (str(param.kind) != 'VAR_POSITIONAL' and str(param.kind) != 'KEYWORD_ONLY' and str(param.kind != 'VAR_KEYWORD')):
            raise ValueError('request parameter must be the last named parameter in function: %s%s'%(fn.__name__,str(sig)))
    return found




#定义RequestHandler,正式向request参数获取URL处理函数所需的参数
class RequestHandler(object):
    #用来封装一个url处理函数。
    #因为定义了__call__属性，一个实例可以看作一个函数

    def __init__(self,app,fn):#接受app参数,这儿的fn是URL处理函数，后面定义
        self._app = app
        self._fn = fn
        self._required_kw_args = get_required_kw_args(fn)
        self._named_kw_args = get_named_kw_args(fn)
        self._has_named_kw_arg = has_named_kw_arg(fn)
        self._has_var_kw_arg = has_var_kw_arg(fn)
        self._has_request_arg = has_request_arg(fn)

    async def __call__(self,request): #__call__这里要构造协程
        kw = None
        if self._has_named_kw_arg or self._has_var_kw_arg:
            #如果有命名关键字或者关键字参数
            if request.method == 'POST': #判断客户端发来的方法是否为POST
                if not request.content_type: #查询有没提交数据的格式（EncType）
                    return web.HTTPBadRequest(text='Missing Content_Type.')#这里被廖大坑了，要有text
                ct = request.content_type.lower() #小写
                if ct.startswith('application/json'): #startswith
                    params = await request.json() #Read request body decoded as json.
                    if not isinstance(params,dict):
                        return web.HTTPBadRequest(text='JSON body must be object.')
                    kw = params
                elif ct.startswith('application/x-www-form-urlencoded') or ct.startswith('multipart/form-data'):
                    params = await request.post() # reads POST parameters from request body.If method is not POST, PUT, PATCH, TRACE or DELETE or content_type is not empty or application/x-www-form-urlencoded or multipart/form-data returns empty multidict.
                    kw = dict(**params)
                else:
                    return web.HTTPBadRequest(text='Unsupported Content_Tpye: %s'%(request.content_type))
            if request.method == 'GET':
                qs = request.query_string #The query string in the URL
                if qs:
                    kw = dict()
                    for k,v in parse.parse_qs(qs,True).items():
                    #Parse a query string given as a string argument.Data are returned as a dictionary. The dictionary keys are the unique query variable names and the values are lists of values for each name.
                        kw[k] = v[0]
        if kw is None:
            kw = dict(**request.match_info)
        else:
            if not self._has_var_kw_arg and self._named_kw_args:
                #当函数参数没有关键字参数时、有命名关键字参数，
                # 移去request中除命名关键字参数所有的参数信息
                copy = dict()
                for name in self._named_kw_args:
                    if name in kw:
                        copy[name] = kw[name]
                kw = copy
            for k,v in request.match_info.items(): #检查命名关键参数
                if k in kw:
                    logging.warning('Duplicate arg name in named arg and kw args: %s' % k)
                kw[k] = v
        if self._has_request_arg:
            kw['request'] = request
        if self._required_kw_args:
            #假如命名关键字参数(没有附加默认值)，request没有提供相应的数值，报错
            for name in self._required_kw_args:
                if name not in kw:
                    return web.HTTPBadRequest(text='Missing argument: %s'%(name))
        logging.info('call with args: %s' % str(kw))

        try:
            r = await self._fn(**kw)
            return r
        except APIError as e: #APIError另外创建
            return dict(error=e.error, data=e.data, message=e.message)



def add_route(app,fn):#编写一个add_route函数，用来注册一个URL处理函数
    method=getattr(fn,'__method__',None)
    path=getattr(fn,'__path__',None)
    if path is None or method is None:
        raise ValueError('@get or @post not defined in %s.' % str(fn))
    if not asyncio.iscoroutinefunction(fn) and not inspect.isgeneratorfunction(fn):
        #如果fn不是一个协程或者也不是一个被协程装饰的函数
        fn = asyncio.coroutine(fn)#将fn变成协程
    logging.info(
        'add route %s %s => %s(%s)' % (method, path, fn.__name__, ', '.join(inspect.signature(fn).parameters.keys())))
    app.router.add_route(method, path, RequestHandler(app, fn))


#直接导入文件，批量注册一个URL处理函数
def add_routes(app,module_name):#module_name应该是存放一系列url处理函数的文件
    n=module_name.rfind('.')#在model_name字符串中查找子字符串'.'的位置，返回坐标。未找到返回-1
    #如果有'.'，那么调用add_routes的函数应该和包名处在同一层级的目录；
    #如果没有'.'，直接导入模块，那么调用add_routes的函数应该和被导入的模块处在同一层级目录。
    if n==-1:
        mod = __import__(module_name, globals(), locals())
    else:
        #如果module_name有'.'的话，应该是：包名.模块名（注意：包名是文件夹名，高一层）
        name=module_name[n+1:]
        #mod=getattr(__import__(module_name[:n],globals(),locals(),[name],0),name)
        #[name]:相当于fromlist = ('name',)，也可以写成[name].
        s=__import__(module_name[:n], globals(), locals(),[name],0)
        mod = getattr(s, name)

    for attr in dir(mod):
        if attr.startswith('_'):#把导入的模块里面本身的属性；例如__builtins__\__cached__\__doc__等过滤掉
            continue
        fn=attr
        if callable(fn):#callable,Python自带的判断对象是否可调用，返回True\False
            method = getattr(fn, '__method__', None)
            path=getattr(fn,'__path__',None)
            if method and path:#我觉得这儿有问题。这儿预先判断method和path是否存在，才进入add_route函数，如果不存在，那这儿怎么继续下去呢？也不报错？
                add_route(app,fn)


def add_static_resource(app):
    #os.path.abspath(__file__)获得当前文件所在路径/目录:D:\PycharmProjects\test_anaconda.py\Dec\test_useless.py
    #os.path.dirname(os.path.abspath(__file__))获得当前文件目录的父目录/上一级目录:D:\PycharmProjects\test_anaconda.py\Dec
    ##输出当前文件夹中'static'的路径:D:\PycharmProjects\test_anaconda.py\Dec\static

    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),'static')
    app.router.add_static('/static/',path)#prefix (str) – URL path prefix for handled static files
    #app.router.add_static必须的两个参数：prefix,path
    #prefix：是静态文件的url的前缀，以/开始，在浏览器地址栏上显示在网站host之后，也用于index.html静态页面进行引用
    #path：静态文件目录的路径，可以是相对路径，上面代码使用的static/css就是相对路径——相对于proxy_server.py所在路径。
    logging.info('add static %s => %s'%('/static/',path))



