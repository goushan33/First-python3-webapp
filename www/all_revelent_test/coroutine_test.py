import threading
import asyncio

@asyncio.coroutine#把一个generator标记为coroutine类型
def hello():
    print('First hello!')
    yield  from asyncio.sleep(1)#可以把asyncio.sleep(1)看作一个耗时1s的io操作。第一个协程执行到这儿的时候，程序并不会等待这儿执行的结果，而是立马执行第二个协程。
    print('Second hello!')

@asyncio.coroutine#把一个generator标记为coroutine类型
def byebye():
    print('First byebye!')
    yield  from asyncio.sleep(1)
    print('Second byebye!')

@asyncio.coroutine
def webget(host):
    print('wget %s...' % host)
    connect = asyncio.open_connection(host, 80)#从网络获取信息，相当于耗时的网络io
    reader, writer = yield from connect
    header = 'GET / HTTP/1.0\r\nHost: %s\r\n\r\n' % host
    writer.write(header.encode('utf-8'))
    yield from writer.drain()#耗时的io操作
    while True:
        line = yield from reader.readline()
        if line == b'\r\n':
            break
        print('%s header > %s' % (host, line.decode('utf-8').rstrip()))
    # Ignore the body, close the socket
    writer.close()

#单线程
tasks=[webget(host) for host in ['www.sina.com.cn', 'www.sohu.com', 'www.163.com']]#封装两个coroutine，可以说两个协程是并发执行的
loop=asyncio.get_event_loop()
loop.run_until_complete(asyncio.wait(tasks))
loop.close()