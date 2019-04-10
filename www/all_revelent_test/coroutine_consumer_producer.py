def consumer():
    r =''#让r位False值
    while True:
        n = yield r
        print('[CONSUMER] Consuming %s...' % n)
        r = '200 OK'

def produce(c):
    c.send(None)#启动生成器，调用consumer(),执行到n=yield r，暂停。返回produce继续执行
    n = 0
    while n < 5:
        n = n + 1
        print('[PRODUCER] Producing %s...' % n)
        r = c.send(n)#此时n==1,将n值发送给consumer()，通过r赋值给n，consumner()继续执行，打印n,将r更新为'200k'，继续执行，在n=yield r暂停，返回produce继续执行，打印r
        print('[PRODUCER] Consumer return: %s' % r)
    c.close()

c = consumer()
produce(c)