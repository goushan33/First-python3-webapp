#aiohttp:是一个http框架，对web开发来说还是较底层；
#为了少写代码，从而产生了web框架，例如：django;
#day5就是学习怎么写一个web框架。web框架需要做如下几件事：
#1、编写url处理函数
#2、传入的参数需要自己从request中获取
#需要构造出Response对象
import functools

def get(path):
    '''
    Define decorator @get('/path')
    '''
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = 'GET'
        wrapper.__route__ = path
        return wrapper
    return decorator

def post(path):
    '''
    Define decorator @get('/path')
    '''
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = 'POST'
        wrapper.__route__ = path
        return wrapper
    return decorator

@get()
def handler1_url(path):
    pass

@post()
def handler2_url(path):
    pass

